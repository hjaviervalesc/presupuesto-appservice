# Calculadora de presupuesto

Aplicación web con Python y Flask que calcula el coste mensual
y anual de una suscripción según el número de usuarios.

## Funcionalidades

- Formulario web.
- Validación de datos en el servidor.
- Cálculo de importes con Decimal.

## Ejecución local

Requiere Python 3.12 y uv.

uv venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe -m flask --app app run

## Objetivo del proyecto

Desplegar la aplicación en Azure App Service mediante GitHub Actions
y comparar la gestión de una plataforma PaaS con una máquina virtual IaaS.

## Estado

Aplicación probada localmente. Despliegue en Azure pendiente.