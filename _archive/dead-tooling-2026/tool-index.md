# 本机工具索引 / Machine Tool Index
> **这是上一台机器的生成物快照，不是本机事实。**下面所有 `<TOOLS>` 都是未探测占位符，不是真实路径。
> 工具没有统一安装根，**禁止把 `<TOOLS>` 换成任何猜测的目录**。要真实路径就本机探测：`Get-Command <工具id> -ErrorAction SilentlyContinue` → 失败则候选列表逐个 `Test-Path` → 全失败即报「缺该工具」。
> 本项目不含 `toolreg/` 注册层，因此**没有 `registry.py resolve`**；不要执行该命令（它在本项目不存在）。


> ⚠️ **本文件由脚本自动生成，每台机器不同，不要手改、不要入库。**
> 原本由旧项目的 `toolreg/` 实测数据生成；本项目不含该层，故所有路径已占位化为 `<TOOLS>`。
> 生成时间：`2026-10-07 06:57:02`

重新生成：`python -u skills\scripts\gen-tool-index.py`

## 工具总览 / Tools

| 工具 | 归属 skill | 可用 | 健康 | 路径 | 版本 | 能力 | 调用方式 |
|---|---|:---:|---|---|---|---|---|
| `7-Zip` | — | ✓ | ok | `C:\Program Files\7-Zip\7z.exe` | — | archive_pack, archive_unpack | `cli:C:\Program Files\7-Zip\7z.exe` |
| `7zFM` | — | ✓ | ok | `C:\Program Files\7-Zip\7zFM.exe` | — | gui_manual_only | `cli:C:\Program Files\7-Zip\7zFM.exe` |
| `CheatEngine` | — | ✓ | ok | `<TOOLS>Debuggers\CE_6.4.3_风叶人加强版\csrss.exe` | — | memory_scan_gui, value_find | `cli:<TOOLS>Debuggers\CE_6.4.3_风叶人加强版\csrss.exe` |
| `FLOSS` | — | ✓ | ok | `<TOOLS>bin\floss.exe` | — | deobfuscate_strings, extract_strings | `cli:<TOOLS>bin\floss.exe --language dotnet {sample}` |
| `Fiddler` | — | ✓ | ok | `<TOOLS>Network_Analyzer\Fiddler\uninst.exe` | — | cli_tool | `cli:<TOOLS>Network_Analyzer\Fiddler\uninst.exe` |
| `Ghidra-headless` | — | ✓ | ok | `<TOOLS>Disassemblers\ghidra_12.0.2_PUBLIC\support\analyzeHeadless.bat` | — | batch_analysis, decompile_native, disassemble_native | `mcp:Ghidra-headless(20 tools,stdio)` |
| `IDA-idat(headless)` | — | ✓ | ok | `<TOOLS>Disassemblers\IDA_Pro_v8.3_Portable\idat.exe` | — | batch_analysis, decompile_native, disassemble_native | `cli:<TOOLS>Disassemblers\IDA_Pro_v8.3_Portable\` |
| `ImHex` | — | ✓ | ok | `<TOOLS>Editors\010 Editor\010Editor.exe` | — | hex_inspect_gui | `cli:<TOOLS>Editors\010 Editor\010Editor.exe` |
| `MCP:pyghidra-mcp` | — | ✓ | ok | `<TOOLS>.venv-tools\Scripts\pyghidra-mcp.exe` | — | mcp_tool | `pylib:MCP:pyghidra-mcp` |
| `PE-bear` | — | ✓ | ok | `<TOOLS>PEtools\PE-bear_0.7.1_qt5_x64_win_vs19\PE-bear.exe` | — | pe_inspect_gui | `cli:<TOOLS>PEtools\PE-bear_0.7.1_qt5_x64_win_vs` |
| `PowerShell` | — | ✓ | ok | `C:\Program Files\PowerShell\7\powershell.exe` | — | cli_tool | `cli:C:\Program Files\PowerShell\7\powershell.exe -NoProfile ` |
| `ResourceHacker` | — | ✓ | ok | `<TOOLS>Editors\Resource_Hacker_v5.2.7\ResourceHacker.exe` | — | cli_tool | `cli:<TOOLS>Editors\Resource_Hacker_v5.2.7\Resou` |
| `Scylla-x64` | — | ✓ | ok | `<TOOLS>PEtools\Scylla.v.0.9.8\Scylla_x64.exe` | — | iat_rebuild, unpack_gui | `cli:<TOOLS>PEtools\Scylla.v.0.9.8\Scylla_x64.ex` |
| `ScyllaHide` | — | ✓ | ok | `<TOOLS>scyllahide\v1.4\InjectorCLIx64.exe` | — | anti_anti_debug | `cli:<TOOLS>scyllahide\v1.4\InjectorCLIx64.exe` |
| `UPX` | — | ✓ | ok | `<TOOLS>PackerAndUnpackers\Unpackers\upxfix\upx.exe` | — | pack_executable, unpack_executable | `cli:<TOOLS>PackerAndUnpackers\Unpackers\upxfix\` |
| `VMProtect` | — | ✓ | ok | `<TOOLS>PackerAndUnpackers\Packers\VMP 系列\VMProtect_3.9.4.exe` | — | cli_tool | `cli:<TOOLS>PackerAndUnpackers\Packers\VMP 系列\VM` |
| `adb` | — | ✓ | ok | `<TOOLS>Android_Tools\搞机工具箱11.0.1\adb.exe` | — | cli_tool | `cli:<TOOLS>Android_Tools\搞机工具箱11.0.1\adb.exe ve` |
| `angr` | — | ✓ | ok | `C:\Users\Administrator\Desktop\飞秋互传.exe` | — | symbolic_execution | `cli:C:\Users\Administrator\Desktop\飞秋互传.exe -c import angr;p` |
| `apktool` | — | ✓ | ok | `<TOOLS>Android_Tools\apktool_2.12.1.jar` | — | rebuild_apk, unpack_apk | `cli:C:\Program Files\Java\jre1.8.0_481\bin\java.exe -jar C:\` |
| `bash` | — | ✓ | ok | `C:\Users\Administrator\.pi\agent\win-git-bash\bin\bash.exe` | — | shell_scripting | `cli:C:\Users\Administrator\.pi\agent\win-git-bash\bin\bash.e` |
| `capa` | — | ✓ | ok | `<TOOLS>bin\capa.exe` | — | behavior_analysis, capability_detection | `cli:<TOOLS>bin\capa.exe -r <TOOLS>capa\rules -j` |
| `capstone` | — | ✓ | ok | `C:\Program Files\Pure Codec\madVR\madHcCtrl.exe` | — | disassembly_lib | `cli:C:\Program Files\Pure Codec\madVR\madHcCtrl.exe -c impor` |
| `cdb` | — | ✓ | ok | `C:\Program Files\Windows Kits\10\Debuggers\x64\cdb.exe` | — | crash_analysis, dump_analysis, kernel_debug | `cli:C:\Program Files\Windows Kits\10\Debuggers\x64\cdb.exe -` |
| `cmake` | — | ✓ | ok | `<TOOLS>mingw64\mingw64\bin\cmake.exe` | — | build_system | `cli:<TOOLS>mingw64\mingw64\bin\cmake.exe --version` |
| `curl(git)` | — | ✓ | ok | `C:\Users\Administrator\.pi\agent\win-git-bash\ucrt64\bin\curl.exe` | — | http_request | `cli:C:\Users\Administrator\.pi\agent\win-git-bash\ucrt64\bin` |
| `de4dot` | — | ✓ | ok | `<TOOLS>NET\de4dot\de4dot.exe` | — | deobfuscate_dotnet, unpack_dotnet | `cli:<TOOLS>NET\de4dot\de4dot.exe --help` |
| `die` | — | ✓ | ok | `<TOOLS>PEtools\DIE_win64_portable_3.11_x64\die.exe` | — | gui_manual_only | `cli:<TOOLS>PEtools\DIE_win64_portable_3.11_x64\` |
| `diec` | — | ✓ | ok | `<TOOLS>PEtools\DIE_win64_portable_3.11_x64\diec.exe` | — | detect_compiler, detect_packer, detect_protector | `cli:<TOOLS>PEtools\DIE_win64_portable_3.11_x64\` |
| `dnSpy` | — | ✓ | ok | `<TOOLS>NET\dnSpy-net-win32\dnSpy.exe` | — | gui_manual_only | `cli:<TOOLS>NET\dnSpy-net-win32\dnSpy.exe` |
| `dnSpy.Console` | — | ✓ | ok | `<TOOLS>NET\dnSpy-net-win32\dnSpy.Console.exe` | — | decompile_dotnet, extract_il | `cli:<TOOLS>NET\dnSpy-net-win32\dnSpy.Console.ex` |
| `dotnet` | — | ✓ | ok | `<TOOLS>dotnet8\dotnet.exe` | — | build_dotnet, run_dotnet_tools | `cli:<TOOLS>dotnet8\dotnet.exe --version` |
| `frida-ps` | — | ✓ | ok | `C:\Users\Administrator\AppData\Roaming\Python\Python314\Scripts\frida.exe` | — | cli_tool | `cli:C:\Users\Administrator\AppData\Roaming\Python\Python314\` |
| `g++` | — | ✓ | ok | `<TOOLS>mingw64\mingw64\bin\g++.exe` | — | compile_cpp | `cli:<TOOLS>mingw64\mingw64\bin\g++.exe --version` |
| `gcc` | — | ✓ | ok | `<TOOLS>mingw64\mingw64\bin\gcc.exe` | — | compile_c, compile_native | `cli:<TOOLS>mingw64\mingw64\bin\gcc.exe --version` |
| `ghidraRun` | — | ✓ | ok | `<TOOLS>Disassemblers\ghidra_12.0.2_PUBLIC\ghidraRun.bat` | — | gui_manual_only | `cli:<TOOLS>Disassemblers\ghidra_12.0.2_PUBLIC\g` |
| `git` | — | ✓ | ok | `C:\Users\Administrator\.pi\agent\win-git-bash\bin\sh.exe` | — | version_control | `cli:C:\Users\Administrator\.pi\agent\win-git-bash\bin\sh.exe` |
| `go` | — | ✓ | ok | `<TOOLS>go\go\bin\go.exe` | — | compile_go | `cli:<TOOLS>go\go\bin\go.exe version` |
| `httpx` | — | ✓ | ok | `<TOOLS>.venv-tools\Scripts\httpx.exe` | — | cli_tool | `cli:C:\Users\Administrator\AppData\Roaming\Python\Python314\` |
| `ida` | — | ✓ | ok | `<TOOLS>Disassemblers\IDA_Pro_v8.3_Portable\ida.exe` | — | gui_manual_only | `cli:<TOOLS>Disassemblers\IDA_Pro_v8.3_Portable\` |
| `ilspycmd` | — | ✓ | ok | `<TOOLS>NET\ILSpy_binaries_8.2.0.7535-x64\ILSpy.exe` | — | decompile_dotnet | `cli:<TOOLS>NET\ILSpy_binaries_8.2.0.7535-x64\IL` |
| `jadx` | — | ✓ | ok | `<TOOLS>Android_Tools\jadx-1.5.3\bin\jadx.bat` | — | decompile_android | `cli:<TOOLS>Android_Tools\jadx-1.5.3\bin\jadx.ba` |
| `java` | — | ✓ | ok | `<TOOLS>jdk21\jdk-21.0.12.1+1\bin\java.exe` | — | run_jar | `cli:<TOOLS>jdk21\jdk-21.0.12.1+1\bin\java.exe -vers` |
| `javac` | — | ✓ | ok | `<TOOLS>jdk21\jdk-21.0.12.1+1\bin\javac.exe` | — | compile_java | `cli:<TOOLS>jdk21\jdk-21.0.12.1+1\bin\javac.exe -ver` |
| `jshookmcp` | — | ✓ | ok | `C:\Users\Administrator\AppData\Local\pi-node\current\npx.cmd` | — | mcp_tool | `cli:C:\Users\Administrator\AppData\Local\pi-node\current\npx` |
| `make` | — | ✓ | ok | `<TOOLS>go\go\src\make.bat` | — | build_make | `cli:<TOOLS>mingw64\mingw64\bin\make.exe --version` |
| `mitmproxy` | — | ✓ | ok | `<TOOLS>Network_Analyzer\mitmproxy\bin\run.ps1` | — | https_mitm, traffic_intercept | `cli:<TOOLS>Network_Analyzer\mitmproxy\bin\run.p` |
| `nmap` | — | ✓ | ok | `<TOOLS>mingw64\mingw64\bin\ctags.exe` | — | port_scan, service_detect | `cli:<TOOLS>mingw64\mingw64\bin\ctags.exe --version` |
| `node` | — | ✓ | ok | `C:\Users\Administrator\AppData\Local\pi-node\current\node.exe` | — | scripting_js | `cli:C:\Users\Administrator\AppData\Local\pi-node\current\nod` |
| `objection` | — | ✓ | ok | `C:\Users\Administrator\AppData\Roaming\Python\Python314\Scripts\objection.exe` | — | mobile_instrumentation, runtime_hook | `cli:C:\Users\Administrator\AppData\Roaming\Python\Python314\` |
| `pe-sieve` | — | ✓ | ok | `<TOOLS>bin\pe-sieve.exe` | — | detect_hooks, detect_injection, memory_dump | `cli:<TOOLS>bin\pe-sieve.exe` |
| `pip` | — | ✓ | ok | `<TOOLS>.venv-tools\Scripts\pip.exe` | — | cli_tool | `cli:<TOOLS>.venv-tools\Scripts\pip.exe --version` |
| `python` | — | ✓ | ok | `<TOOLS>.venv-tools\Scripts\python.exe` | — | pylib_host, scripting | `cli:<TOOLS>.venv-tools\Scripts\python.exe -V` |
| `qiling` | — | ✓ | ok | `<TOOLS>.venv-tools\Scripts\qltui.py` | — | os_emulation | `cli:<TOOLS>.venv-tools\Scripts\qltui.py -c import qiling;p` |
| `r2pm` | — | ✓ | ok | `<TOOLS>radare2\radare2-6.2.4-w64\bin\r2pm.exe` | — | cli_tool | `cli:<TOOLS>radare2\radare2-6.2.4-w64\bin\r2pm.exe -` |
| `rabin2` | — | ✓ | ok | `<TOOLS>radare2\radare2-6.2.4-w64\bin\rabin2.exe` | — | cli_tool | `cli:<TOOLS>radare2\radare2-6.2.4-w64\bin\rabin2.exe` |
| `radare2` | — | ✓ | ok | `<TOOLS>bin\radare2.cmd` | — | analyze_binary, disassemble_native, extract_strings_cli | `cli:<TOOLS>bin\radare2.cmd -q -e scr.color=0` |
| `radiff2` | — | ✓ | ok | `<TOOLS>radare2\radare2-6.2.4-w64\bin\radiff2.exe` | — | cli_tool | `cli:<TOOLS>radare2\radare2-6.2.4-w64\bin\radiff2.ex` |
| `rahash2` | — | ✓ | ok | `<TOOLS>radare2\radare2-6.2.4-w64\bin\rahash2.exe` | — | cli_tool | `cli:<TOOLS>radare2\radare2-6.2.4-w64\bin\rahash2.ex` |
| `rasm2` | — | ✓ | ok | `<TOOLS>radare2\radare2-6.2.4-w64\bin\rasm2.exe` | — | cli_tool | `cli:<TOOLS>radare2\radare2-6.2.4-w64\bin\rasm2.exe ` |
| `rax2` | — | ✓ | ok | `<TOOLS>radare2\radare2-6.2.4-w64\bin\rax2.exe` | — | cli_tool | `cli:<TOOLS>radare2\radare2-6.2.4-w64\bin\rax2.exe` |
| `tshark` | — | ✓ | ok | `<TOOLS>Network_Analyzer\WiresharkPortable64\WiresharkPortable64.exe` | — | pcap_read, protocol_analysis, traffic_capture | `cli:<TOOLS>Network_Analyzer\WiresharkPortable64` |
| `unicorn` | — | ✓ | ok | `<TOOLS>mingw64\mingw64\bin\doxygen.exe` | — | cpu_emulation | `cli:<TOOLS>mingw64\mingw64\bin\doxygen.exe -c impor` |
| `wireshark` | — | ✓ | ok | `<TOOLS>Network_Analyzer\WiresharkPortable64\App\Wireshark\Wireshark.exe` | — | gui_manual_only | `cli:<TOOLS>Network_Analyzer\WiresharkPortable64` |
| `x64dbg` | — | ✓ | ok | `<TOOLS>Debuggers\x64dbg\release\x64\x64dbg.exe` | — | gui_manual_only | `cli:<TOOLS>Debuggers\x64dbg\release\x64\x64dbg.` |
| `x64dbg-headless` | — | ✓ | ok | `<TOOLS>Debuggers\x64dbg\release\x96dbg.exe` | — | dynamic_debug, mcp_endpoint, read_memory | `mcp:x64dbg-headless(80 tools,http)` |
| `yara` | — | ✓ | ok | `<TOOLS>Anti Rootkit\WKE32\WindowsKernelExplorer.exe` | — | pattern_match, signature_scan | `cli:<TOOLS>Anti Rootkit\WKE32\WindowsKernelExpl` |
| `z3` | — | ✓ | ok | `<TOOLS>bin\fd.exe` | — | constraint_solving | `cli:<TOOLS>bin\fd.exe -c import z3;print('Z3',z3.ge` |
| `zipalign` | — | ✓ | ok | `<TOOLS>Android_Tools\ApkIDE_v3.3\ApkIDE\zipalign.exe` | — | cli_tool | `cli:<TOOLS>Android_Tools\ApkIDE_v3.3\ApkIDE\zip` |
| `ConfuserEx` | — | ✗ | no-path | `—` | — | obfuscate_dotnet, protect_dotnet | `pylib:ConfuserEx` |
| `Frida` | — | ✗ | no-path | `—` | — | api_trace, instrumentation, runtime_hook | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Pyt` |
| `InnoSetup` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:InnoSetup` |
| `MCP:x64dbg` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:MCP:x64dbg` |
| `NSIS` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:NSIS` |
| `Npcap` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:Npcap` |
| `Platform-tools` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:Platform-tools` |
| `Protector` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:Protector` |
| `Wireshark(iflist)` | — | ✗ | no-path | `—` | — | list_capture_interfaces | `pylib:Wireshark(iflist)` |
| `agent-browser` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:agent-browser` |
| `apksigner` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:apksigner` |
| `binaryninja` | — | ✗ | no-path | `—` | — | gui_manual_only | `pylib:binaryninja` |
| `binwalk` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:binwalk` |
| `bkcrack` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:bkcrack` |
| `cargo` | — | ✗ | no-path | `—` | — | build_rust | `pylib:cargo` |
| `construct` | — | ✗ | no-path | `—` | — | binary_struct_parse | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Pyt` |
| `dnsx` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:dnsx` |
| `ffuf` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:ffuf` |
| `git-bash-timeout` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:git-bash-timeout` |
| `gobuster` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:gobuster` |
| `ida-pro-mcp` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:ida-pro-mcp` |
| `idalib-mcp` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:idalib-mcp` |
| `innoextract` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:innoextract` |
| `innounp` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:innounp` |
| `jeb-pro` | — | ✗ | no-path | `—` | — | gui_manual_only | `pylib:jeb-pro` |
| `katana` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:katana` |
| `lief` | — | ✗ | no-path | `—` | — | binary_patch, pe_modify | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Pyt` |
| `naabu` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:naabu` |
| `npx` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:npx` |
| `nuclei` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:nuclei` |
| `pefile` | — | ✗ | ok | `—` | 2024.8.26 | pe_imports, pe_parse, pe_sections | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Pyt` |
| `pentestswarm` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:pentestswarm` |
| `pi:mcp.json` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:pi:mcp.json` |
| `playwright` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:playwright` |
| `proxycat` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:proxycat` |
| `pwntools` | — | ✗ | no-path | `—` | — | python_library | `pylib:pwntools` |
| `pyghidra-mcp` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:pyghidra-mcp` |
| `r2gui` | — | ✗ | no-path | `—` | — | gui_manual_only | `pylib:r2gui` |
| `r2mcp` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:r2mcp` |
| `r2xsql` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:r2xsql` |
| `r2xsql-full` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:r2xsql-full` |
| `radius2` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:radius2` |
| `reqable-mcp` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:reqable-mcp` |
| `rustc` | — | ✗ | no-path | `—` | — | compile_rust | `pylib:rustc` |
| `seclists` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:seclists` |
| `sqlmap` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:sqlmap` |
| `subfinder` | — | ✗ | no-path | `—` | — | cli_tool | `pylib:subfinder` |
| `triton` | — | ✗ | no-path | `—` | — | python_library | `pylib:triton` |
| `x64dbg-MCP-plugin` | — | ✗ | no-path | `—` | — | mcp_dynamic_debug | `pylib:x64dbg-MCP-plugin` |
| `x64dbg-mcp-daemon` | — | ✗ | no-path | `—` | — | start_mcp_debugger | `pylib:x64dbg-mcp-daemon` |
| `xquik-mcp` | — | ✗ | no-path | `—` | — | mcp_tool | `pylib:xquik-mcp` |

## 能力状态视图 / Capability Status

| 能力 | 就绪工具 | 调用方式 |
|---|---|---|
| analyze_binary | radare2 | `cli:<TOOLS>bin\radare2.cmd -q -e scr.color=0` |
| anti_anti_debug | ScyllaHide | `cli:<TOOLS>scyllahide\v1.4\InjectorCLIx64.exe` |
| api_trace | — | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Python314\pyt` |
| archive_pack | 7-Zip | `cli:C:\Program Files\7-Zip\7z.exe` |
| archive_unpack | 7-Zip | `cli:C:\Program Files\7-Zip\7z.exe` |
| batch_analysis | Ghidra-headless, IDA-idat(headless) | `mcp:Ghidra-headless(20 tools,stdio)` |
| behavior_analysis | capa | `cli:<TOOLS>bin\capa.exe -r <TOOLS>capa\rules -j` |
| binary_patch | — | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Python314\pyt` |
| binary_struct_parse | — | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Python314\pyt` |
| build_dotnet | dotnet | `cli:<TOOLS>dotnet8\dotnet.exe --version` |
| build_make | make | `cli:<TOOLS>mingw64\mingw64\bin\make.exe --version` |
| build_rust | — | `pylib:cargo` |
| build_system | cmake | `cli:<TOOLS>mingw64\mingw64\bin\cmake.exe --version` |
| capability_detection | capa | `cli:<TOOLS>bin\capa.exe -r <TOOLS>capa\rules -j` |
| cli_tool | PowerShell, httpx, Fiddler, ResourceHacker, VMProtect, adb, zipalign, frida-ps, rabin2, rasm2, radiff2, rahash2, rax2, r2pm, pip | `cli:C:\Program Files\PowerShell\7\powershell.exe -NoProfile -Command $` |
| compile_c | gcc | `cli:<TOOLS>mingw64\mingw64\bin\gcc.exe --version` |
| compile_cpp | g++ | `cli:<TOOLS>mingw64\mingw64\bin\g++.exe --version` |
| compile_go | go | `cli:<TOOLS>go\go\bin\go.exe version` |
| compile_java | javac | `cli:<TOOLS>jdk21\jdk-21.0.12.1+1\bin\javac.exe -version` |
| compile_native | gcc | `cli:<TOOLS>mingw64\mingw64\bin\gcc.exe --version` |
| compile_rust | — | `pylib:rustc` |
| constraint_solving | z3 | `cli:<TOOLS>bin\fd.exe -c import z3;print('Z3',z3.get_version_` |
| cpu_emulation | unicorn | `cli:<TOOLS>mingw64\mingw64\bin\doxygen.exe -c import unicorn;` |
| crash_analysis | cdb | `cli:C:\Program Files\Windows Kits\10\Debuggers\x64\cdb.exe -version` |
| decompile_android | jadx | `cli:<TOOLS>Android_Tools\jadx-1.5.3\bin\jadx.bat --versio` |
| decompile_dotnet | dnSpy.Console, ilspycmd | `cli:<TOOLS>NET\dnSpy-net-win32\dnSpy.Console.exe --help` |
| decompile_native | Ghidra-headless, IDA-idat(headless) | `mcp:Ghidra-headless(20 tools,stdio)` |
| deobfuscate_dotnet | de4dot | `cli:<TOOLS>NET\de4dot\de4dot.exe --help` |
| deobfuscate_strings | FLOSS | `cli:<TOOLS>bin\floss.exe --language dotnet {sample}` |
| detect_compiler | diec | `cli:<TOOLS>PEtools\DIE_win64_portable_3.11_x64\diec.exe -` |
| detect_hooks | pe-sieve | `cli:<TOOLS>bin\pe-sieve.exe` |
| detect_injection | pe-sieve | `cli:<TOOLS>bin\pe-sieve.exe` |
| detect_packer | diec | `cli:<TOOLS>PEtools\DIE_win64_portable_3.11_x64\diec.exe -` |
| detect_protector | diec | `cli:<TOOLS>PEtools\DIE_win64_portable_3.11_x64\diec.exe -` |
| disassemble_native | Ghidra-headless, radare2, IDA-idat(headless) | `mcp:Ghidra-headless(20 tools,stdio)` |
| disassembly_lib | capstone | `cli:C:\Program Files\Pure Codec\madVR\madHcCtrl.exe -c import capstone` |
| dump_analysis | cdb | `cli:C:\Program Files\Windows Kits\10\Debuggers\x64\cdb.exe -version` |
| dynamic_debug | x64dbg-headless | `mcp:x64dbg-headless(80 tools,http)` |
| extract_il | dnSpy.Console | `cli:<TOOLS>NET\dnSpy-net-win32\dnSpy.Console.exe --help` |
| extract_strings | FLOSS | `cli:<TOOLS>bin\floss.exe --language dotnet {sample}` |
| extract_strings_cli | radare2 | `cli:<TOOLS>bin\radare2.cmd -q -e scr.color=0` |
| gui_manual_only | ida, dnSpy, die, wireshark, x64dbg, 7zFM, ghidraRun | `cli:<TOOLS>Disassemblers\IDA_Pro_v8.3_Portable\ida.exe` |
| hex_inspect_gui | ImHex | `cli:<TOOLS>Editors\010 Editor\010Editor.exe` |
| http_request | curl(git) | `cli:C:\Users\Administrator\.pi\agent\win-git-bash\ucrt64\bin\curl.exe ` |
| https_mitm | mitmproxy | `cli:<TOOLS>Network_Analyzer\mitmproxy\bin\run.ps1 -m mitm` |
| iat_rebuild | Scylla-x64 | `cli:<TOOLS>PEtools\Scylla.v.0.9.8\Scylla_x64.exe` |
| identify_filetype | diec | `cli:<TOOLS>PEtools\DIE_win64_portable_3.11_x64\diec.exe -` |
| instrumentation | — | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Python314\pyt` |
| kernel_debug | cdb | `cli:C:\Program Files\Windows Kits\10\Debuggers\x64\cdb.exe -version` |
| list_capture_interfaces | — | `pylib:Wireshark(iflist)` |
| mcp_dynamic_debug | — | `pylib:x64dbg-MCP-plugin` |
| mcp_endpoint | Ghidra-headless, x64dbg-headless | `mcp:Ghidra-headless(20 tools,stdio)` |
| mcp_tool | MCP:pyghidra-mcp, jshookmcp | `pylib:MCP:pyghidra-mcp` |
| memory_dump | pe-sieve | `cli:<TOOLS>bin\pe-sieve.exe` |
| memory_scan_gui | CheatEngine | `cli:<TOOLS>Debuggers\CE_6.4.3_风叶人加强版\csrss.exe` |
| mobile_instrumentation | objection | `cli:C:\Users\Administrator\AppData\Roaming\Python\Python314\Scripts\ob` |
| obfuscate_dotnet | — | `pylib:ConfuserEx` |
| os_emulation | qiling | `cli:<TOOLS>.venv-tools\Scripts\qltui.py -c import qiling;print('QILI` |
| pack_executable | UPX | `cli:<TOOLS>PackerAndUnpackers\Unpackers\upxfix\upx.exe --` |
| pattern_match | yara | `cli:<TOOLS>Anti Rootkit\WKE32\WindowsKernelExplorer.exe -` |
| pcap_read | tshark | `cli:<TOOLS>Network_Analyzer\WiresharkPortable64\Wireshark` |
| pe_imports | — | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Python314\pyt` |
| pe_inspect_gui | PE-bear | `cli:<TOOLS>PEtools\PE-bear_0.7.1_qt5_x64_win_vs19\PE-bear` |
| pe_modify | — | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Python314\pyt` |
| pe_parse | — | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Python314\pyt` |
| pe_sections | — | `cli:C:\Users\Administrator\AppData\Local\Programs\Python\Python314\pyt` |
| port_scan | nmap | `cli:<TOOLS>mingw64\mingw64\bin\ctags.exe --version` |
| protect_dotnet | — | `pylib:ConfuserEx` |
| protocol_analysis | tshark | `cli:<TOOLS>Network_Analyzer\WiresharkPortable64\Wireshark` |
| pylib_host | python | `cli:<TOOLS>.venv-tools\Scripts\python.exe -V` |
| python_library | — | `pylib:triton` |
| read_memory | x64dbg-headless | `mcp:x64dbg-headless(80 tools,http)` |
| rebuild_apk | apktool | `cli:C:\Program Files\Java\jre1.8.0_481\bin\java.exe -jar <TOOLS>apk` |
| registers | x64dbg-headless | `mcp:x64dbg-headless(80 tools,http)` |
| run_dotnet_tools | dotnet | `cli:<TOOLS>dotnet8\dotnet.exe --version` |
| run_jar | java | `cli:<TOOLS>jdk21\jdk-21.0.12.1+1\bin\java.exe -version` |
| runtime_hook | objection | `cli:C:\Users\Administrator\AppData\Roaming\Python\Python314\Scripts\ob` |
| scripting | python | `cli:<TOOLS>.venv-tools\Scripts\python.exe -V` |
| scripting_js | node | `cli:C:\Users\Administrator\AppData\Local\pi-node\current\node.exe -v` |
| service_detect | nmap | `cli:<TOOLS>mingw64\mingw64\bin\ctags.exe --version` |
| set_breakpoint | x64dbg-headless | `mcp:x64dbg-headless(80 tools,http)` |
| shell_scripting | bash | `cli:C:\Users\Administrator\.pi\agent\win-git-bash\bin\bash.exe -c echo` |
| signature_scan | yara | `cli:<TOOLS>Anti Rootkit\WKE32\WindowsKernelExplorer.exe -` |
| start_mcp_debugger | — | `pylib:x64dbg-mcp-daemon` |
| step | x64dbg-headless | `mcp:x64dbg-headless(80 tools,http)` |
| symbolic_execution | angr | `cli:C:\Users\Administrator\Desktop\飞秋互传.exe -c import angr;print('ANGR` |
| traffic_capture | tshark | `cli:<TOOLS>Network_Analyzer\WiresharkPortable64\Wireshark` |
| traffic_intercept | mitmproxy | `cli:<TOOLS>Network_Analyzer\mitmproxy\bin\run.ps1 -m mitm` |
| unpack_apk | apktool | `cli:C:\Program Files\Java\jre1.8.0_481\bin\java.exe -jar <TOOLS>apk` |
| unpack_dotnet | de4dot | `cli:<TOOLS>NET\de4dot\de4dot.exe --help` |
| unpack_executable | UPX | `cli:<TOOLS>PackerAndUnpackers\Unpackers\upxfix\upx.exe --` |
| unpack_gui | Scylla-x64 | `cli:<TOOLS>PEtools\Scylla.v.0.9.8\Scylla_x64.exe` |
| value_find | CheatEngine | `cli:<TOOLS>Debuggers\CE_6.4.3_风叶人加强版\csrss.exe` |
| version_control | git | `cli:C:\Users\Administrator\.pi\agent\win-git-bash\bin\sh.exe --version` |

## MCP 端点 / MCP Endpoints

| 名称 | 类型 | 工具数 | 状态 | 端点/命令 | 备注 |
|---|---|:---:|---|---|---|
| `x64dbg` | http | 80 | ready | `http://127.0.0.1:9094/mcp` | x64dbg GUI 必须在运行（插件活在被调试进程里，端口才监听） |
| `ghidra` | stdio | 20 | ready | `<TOOLS>bin\ghidra-mcp.cmd` | JAVA_HOME 指向 JDK21+（Ghidra 12 要求），GHIDRA_INSTALL_D |

## 汇总 / Summary

- 工具总数：119 ｜ 可用：68 ｜ 不可用：51 ｜ 能力项：94 ｜ MCP：2
- 不可用工具（需要时按 registry 的 install 指引补装）：`ConfuserEx`, `Frida`, `InnoSetup`, `MCP:x64dbg`, `NSIS`, `Npcap`, `Platform-tools`, `Protector`, `Wireshark(iflist)`, `agent-browser`, `apksigner`, `binaryninja`, `binwalk`, `bkcrack`, `cargo`, `construct`, `dnsx`, `ffuf`, `git-bash-timeout`, `gobuster`

