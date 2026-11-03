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


def apply_windows_host_patches(source):
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