#!/bin/bash
# Script wrapper para ejecutar reporte diario con el venv correcto
# Usado por launchd (com.cathpro.dailyreport.plist)

cd /Users/veronicavelasquez/Desktop/DEVS/cathpro-dashboard

# Activar virtual environment
source .venv/bin/activate

# Ejecutar script de reporte (usar python3 explícitamente)
python3 daily_report.py

# Desactivar venv
deactivate
