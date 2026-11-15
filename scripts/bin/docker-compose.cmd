@echo off
wsl.exe -u root -d Ubuntu -- docker-compose %*
