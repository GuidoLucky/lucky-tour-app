# Cotizador de Vuelos — Lucky Tour

App web para generar cotizaciones en PDF a partir de capturas de Sabre/Amadeus.

## Deploy en Railway

1. Subí esta carpeta a un repositorio de GitHub (público o privado)
2. En Railway: **New Project → Deploy from GitHub repo**
3. Seleccioná el repo
4. Andá a **Variables** y agregá estas dos:
   - `ANTHROPIC_API_KEY` → tu API key de Anthropic
   - `SECRET_KEY` → cualquier string largo (ej: `lucky-tour-2024-xyz`)
5. Railway lo deploya automáticamente

## Uso

1. Abrí la URL que te da Railway
2. Subí las capturas de Sabre/Amadeus (itinerario + tarifas)
3. Completá vendedor y cantidad de pasajeros
4. Descargá el PDF

## Estructura

```
lucky-tour-app/
├── app.py              # Backend Flask
├── requirements.txt    # Dependencias
├── Procfile            # Configuración Railway
├── templates/
│   └── index.html      # Interfaz web
└── static/
    └── logo.png        # Logo Lucky Tour
```
