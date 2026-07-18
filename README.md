# bahía

**El carro entra. La certeza sale.**

Software profesional para taller + repuestos.  
Instalación vacía (sin demos). Puede correr en su PC **o en la nube 24/7** sin depender de una computadora local.

## Opción A — En la nube (recomendado)

El taller queda online aunque apague su PC.

1. Ejecute `Publicar-En-La-Nube.bat`  
   (sube el código a GitHub y abre Render)
2. En Render: **Apply** el blueprint `bahia-taller`
3. Entre a la URL `https://….onrender.com`
4. Usuario: `admin`  
   Clave: la de la variable `BAHIA_ADMIN_PASSWORD` en Render → Environment

Variables importantes:

| Variable | Para qué |
|----------|----------|
| `BAHIA_SECRET_KEY` | Seguridad (Render la genera) |
| `BAHIA_ADMIN_PASSWORD` | Clave del dueño |
| `BAHIA_DATA_DIR=/data` | Guarda bodega, OT y fotos en disco persistente |
| `PUBLIC_BASE_URL` | Se llena sola con `RENDER_EXTERNAL_URL` |

## Opción B — En un servidor propio (Docker)

```bash
export BAHIA_SECRET_KEY=clave-larga
export BAHIA_ADMIN_PASSWORD=clave-del-dueno
docker compose up -d --build
```

Queda en `http://SERVIDOR:8096`

## Opción C — Solo en esta PC (local)

`Iniciar-TallerPro.bat` → [http://127.0.0.1:8096/login](http://127.0.0.1:8096/login)

Para borrar todo y empezar vacío: `Limpiar-Y-Empezar.bat`

## Primer uso (siempre vacío)

1. Entrar como admin  
2. **Casa** → nombre del taller, WhatsApp, tarifa  
3. Crear usuarios del equipo  
4. Cargar proveedores y estantería  
5. Recibir el primer vehículo  
