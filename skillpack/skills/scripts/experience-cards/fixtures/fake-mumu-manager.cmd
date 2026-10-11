@echo off
REM 假 MuMuManager.exe —— 复刻官方 `info -v all` 的 JSON 输出结构（官方文档字段表）。
REM 用途：验证 emulator-lab.ps1 的 MuMu JSON 解析路径在**没有真 MuMu** 时也能被测到。
REM 行为随环境变量 MUMU_FIXTURE 变化：
REM   MUMU_FIXTURE=single  默认：实例 0 已启动（16384），实例 1 未启动（16416）
REM   MUMU_FIXTURE=empty   全部未启动（无 adb_port）
REM   MUMU_FIXTURE=bare    不输出任何 JSON（模拟老版本只打标题）
if "%MUMU_FIXTURE%"=="empty" goto empty
if "%MUMU_FIXTURE%"=="bare" goto bare
echo [
echo   {
echo     "adb_host_ip": "127.0.0.1",
echo     "adb_port": 16384,
echo     "created_timestamp": 1721180910349678,
echo     "disk_size_bytes": 284192948,
echo     "error_code": 0,
echo     "headless_pid": 20868,
echo     "hyperv_enabled": false,
echo     "index": "0",
echo     "is_android_started": true,
echo     "is_main": true,
echo     "is_process_started": true,
echo     "launch_err_code": 0,
echo     "launch_err_msg": "",
echo     "name": "fixture-instance-0",
echo     "pid": 15112,
echo     "player_state": "running",
echo     "vt_enabled": true
echo   },
echo   {
echo     "adb_host_ip": "127.0.0.1",
echo     "adb_port": 16416,
echo     "index": "1",
echo     "is_android_started": false,
echo     "is_main": false,
echo     "is_process_started": false,
echo     "name": "fixture-instance-1",
echo     "pid": 0
echo   }
echo ]
exit /b 0
:empty
echo []
exit /b 0
:bare
echo MuMuManager Console v4.0.0.3179
echo No instance information available.
exit /b 0