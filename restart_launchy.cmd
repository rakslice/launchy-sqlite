taskkill /im Launchy.exe /f

:LOOP
timeout /t 1 /nobreak > NUL

QPROCESS "Launchy.exe">NUL
IF %ERRORLEVEL% EQU 0 GOTO LOOP

erase stderr.txt
erase stdout.txt

cd %~dp0..\..
start Launchy.exe
