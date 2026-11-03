"""GN patches that let Chromium's Windows toolchain host an Android V8 build.

Chromium only supports Android cross builds from Linux hosts. The Chromium
build config vendored into the published v8 crate therefore asserts a Linux
host, and it only defines the x64-host/arm64-target generator toolchain under
//build/toolchain/linux. Operit2's Windows CI builds the Android V8 from
source, so the Windows toolchain files are relaxed and gain the same generator
toolchain that Linux provides.
"""

ASSERT_OLD = 'assert(is_win, "Should only be running on Windows")'

ASSERT_NEW = """assert(is_win || host_os == "win",
       "Should only be running on Windows (or hosting an Android cross build)")"""

TOOLCHAIN_BLOCK = """# Added by Operit2's prepare_android_v8.py: Chromium only defines the V8
# generator toolchain for Linux hosts, but an Android arm64 cross build from a
# Windows host needs the same x64-host/arm64-target toolchain that
# //build/toolchain/linux provides for Linux hosts.
if (target_cpu == "arm64") {
  win_toolchains("x64_v8_arm64") {
    toolchain_arch = "x64"
    clang_toolchain_prefix = "clang_"
    toolchain_args = {
      v8_current_cpu = "arm64"
    }
  }
}
"""


def _relax_assert(source, name):
    path = source / name
    content = path.read_text()
    if ASSERT_OLD in content:
        path.write_text(content.replace(ASSERT_OLD, ASSERT_NEW, 1))


def _android_rt_lib_dir(ndk):
    """Return the NDK directory holding the Android compiler-rt builtins."""
    prebuilt = ndk / "toolchains/llvm/prebuilt"
    if not prebuilt.is_dir():
        return None
    for host in sorted(prebuilt.iterdir()):
        clang = host / "lib/clang"
        if not clang.is_dir():
            continue
        for version in sorted(clang.iterdir()):
            lib_dir = version / "lib"
            if (lib_dir / "linux/libclang_rt.builtins-aarch64-android.a").is_file():
                return lib_dir
    return None


def _patch_android_rtlib(source, ndk):
    """Point Android builds at the NDK compiler-rt builtins.

    Chromium's clang_lib() template resolves compiler-rt relative to
    clang_base_path, which on Windows is the Chromium clang package: it ships
    Windows runtimes only, so GN demands a libclang_rt.builtins-aarch64-android.a
    that never exists and ninja fails with "missing and no known rule".
    The NDK ships exactly that library, so Android toolchains use it instead.
    """
    lib_dir = _android_rt_lib_dir(ndk)
    if lib_dir is None:
        return
    build_gn = source / "build/config/clang/BUILD.gn"
    content = build_gn.read_text()
    marker = '_clang_lib_dir = "$clang_base_path/lib/clang/$clang_version/lib"'
    if marker not in content or "use the NDK copy" in content:
        return
    newline = chr(10)
    replacement = (
        marker
        + newline + "      # Added by Operit2: the Chromium clang package for Windows"
        + newline + "      # ships no Android compiler-rt, so Android targets use the NDK copy."
        + newline + "      if (is_android) {"
        + newline + '        _clang_lib_dir = "' + lib_dir.as_posix() + '"'
        + newline + "      }"
    )
    assert '"' not in lib_dir.as_posix(), "NDK path contains a quote"
    build_gn.write_text(content.replace(marker, replacement, 1))


def apply_windows_host_patches(source, ndk=None):
    """Relax the Windows toolchain host checks and add the missing toolchain.

    The Windows toolchain files are loaded while the default toolchain targets
    Android, where is_win is false, so their host assertions have to accept a
    Windows host as well. The generator toolchain itself is the regular
    Windows clang x64 toolchain with v8_current_cpu forwarded, mirroring
    //build/toolchain/linux:clang_x64_v8_arm64.
    """
    _relax_assert(source, "build/toolchain/win/BUILD.gn")
    _relax_assert(source, "build/toolchain/win/toolchain.gni")
    build_gn = source / "build/toolchain/win/BUILD.gn"
    content = build_gn.read_text().replace(
        'if (current_toolchain == default_toolchain) {',
        'if (is_win && current_toolchain == default_toolchain) {',
        1,
    )
    if 'win_toolchains("x64_v8_arm64")' not in content:
        content += TOOLCHAIN_BLOCK
    build_gn.write_text(content)
    if ndk is not None:
        _patch_android_rtlib(source, ndk)