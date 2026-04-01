@ECHO OFF
IF [%1] == [] (
	ECHO Using Default profile, pass your profile name if you want to use one
	start "EDMD" python edmd.py
) ELSE (
	ECHO Using profile %1
	start "EDMD" python edmd.py -p %1
)