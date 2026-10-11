@echo off
REM Fake native tool used by the experience-card fixtures.
REM Prints a marker on stdout, a diagnostic on stderr (the thing that breaks
REM PowerShell's strict mode), then exits with the code given as argv[1].
echo FIXTURE-STDOUT-MARKER
echo FIXTURE-STDERR-DIAGNOSTIC 1>&2
if "%~1"=="" exit /b 0
exit /b %~1