# Windows — extract and run

Target: Windows x86-64 Intel/AMD with PowerShell 5.1 or newer. Extract **all** files to a writable local path such as `C:\BRiDCT`, open `bridct`, then double-click `run_windows.cmd`.

The launcher downloads private Python and MSYS2/Clang tools with pinned hashes, installs public benchmark libraries, compiles C11, validates numerical outputs, and runs two short comparison sessions. Internet and several GB of free disk space are needed. No administrator installation or permanent PATH change is made. Corporate download policies may block execution; the failure is logged.

Optional commands from a terminal:

```bat
.\run_windows.cmd -Profile Verify
.\run_windows.cmd -Profile Full
.\run_windows.cmd -Jobs 2
```

`Verify` builds and checks without timing. Default `Quick` uses ten shapes, two sessions of seven blocks calibrated to 10 ms. `Full` covers all 64 shapes with 21 blocks calibrated to 30 ms. Comparisons include OpenCV, SciPy, DUCC, pyFFTW and separately attributed native C Ooura controls. Apple vDSP is unavailable on Windows.

Read `results\windows-...\status.txt`, summary and logs, and retain `results\windows-....zip`, including on failure. Success requires `exit_code=0` and `last_stage=complete`; the ZIP alone is not evidence of success. CPU/RAM/Windows, compilers, package versions, source hashes, checks and timing records are included. No results are uploaded. Logs can contain local paths; review them before public sharing.

The dev.7 kernels completed numerical checks on a native Windows 11 i9-9820X workstation. That short screen retained performance losses, especially at 1024×1024. This repackaging does not claim a new Windows execution or universal Intel/AMD speedup. All library paths use Shao–Johnson. See `docs/PLATFORMS.md`.
