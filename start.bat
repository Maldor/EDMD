@ECHO OFF
IF [%1] == [] (
    ECHO Using Default profile. Pass your profile name as an argument to use one.
    start "EDMD" python edmd.py --mode textual
) ELSE (
    ECHO Using profile %1
    start "EDMD" python edmd.py -p %1 --mode textual
)
