if "%1"=="da" (
	goto delall
) else (
	goto delini
)

:delall
	set /p input="del all files?(y/n)"
	if "%input%"=="y" (
		rd /q /s "C:\Users\Administrator\AppData\Roaming\MailEnhance\profile"
	)
	goto startup
	
:delini
	del "C:\Users\Administrator\AppData\Roaming\MailEnhance\profile\1g6nwp1n.default\compatibility.ini"
	del "C:\Users\Administrator\AppData\Roaming\MailEnhance\profiles.ini"
	goto startup
	
:startup
	F:\thinkmail\src\github\MailEnhance\MailEnhance\obj_MailEnhance\mozilla\dist\bin\SFmail.exe

:end
