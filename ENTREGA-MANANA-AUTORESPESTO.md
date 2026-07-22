# Entrega mañana — Cliente 1: Autorespuesto (Katire)

Documento interno del **vendor**. No entregar la parte de secretos al personal operativo del taller.

## Panel VENDOR (usted — dueño del software)

URL: https://katire.onrender.com/vendor  

- Usuario: `katire`  
- Clave: `KatireVendor2026` *(cámbiela en Render: `KATIRE_VENDOR_USER` / `KATIRE_VENDOR_PASSWORD`)*

Desde ahí usted:
1. Emite licencias para otros talleres (**2 dispositivos** por defecto)
2. Crea usuarios y contraseñas del taller
3. Ve y libera dispositivos si el cliente cambió de PC
4. Copia la clave `KT1....` para entregarla al nuevo taller

El **admin del taller** (`admin`) no es usted: es el dueño de Autorespuesto. Usted es **Vendor**.

## Dispositivos

Cada licencia permite **2 dispositivos** (PC + tablet, o 2 PCs).  
Al tercer equipo el login se bloquea hasta que usted libere uno en el panel Vendor.

1. URL: https://katire.onrender.com  
2. Usuario dueño del taller: `admin` / `DuenoKatire2026` (cámbiela el día 1)  
3. Usuario recepción (opcional): `cliente` / `VerKatire2026`  
4. Licencia activa hasta **2027-07-21** (8 puestos)  

Clave de lanzamiento Autorespuesto (activar si hace falta):

```
KT1.eyJ2IjoxLCJzaG9wIjoiQXV0b3Jlc3B1ZXN0byIsImV4cCI6IjIwMjctMDctMjEiLCJzZWF0cyI6OCwibm90ZSI6IkNsaWVudGUxIiwiaXNzdWVkIjoiMjAyNi0wNy0yMSJ9.pGJfMMDuOpsn1as1uHE6Q93jOy9mOZTimgV4njKHG4M
```

(En producción el taller activa la licencia al entrar: usuario/clave + pegar clave KT1… si el sistema la pide.)

5. Capacitación: Patio, Ingreso, Diagnóstico/croqui, Estantería (pistola), Factura  

**No recibe:** código fuente, `/docs` API, script `issue_license.py`, secreto de firma, ni permiso de reventa.

## Qué ve cada rol

| Rol | Sistema |
|-----|---------|
| Recepción / mecánico | Patio, Ingreso, Diagnóstico, Bodega, Tiendas, Aliados, emitir comprobantes |
| Admin taller | Todo lo anterior + **Casa (Administración)**: identidad, usuarios, emisor Hacienda, .p12 |
| Vendor (ustedes) | Emiten licencias, cobran, dan soporte |

La API Swagger (`/docs`) está **apagada en producción**. El cliente no “ve la API”.

## Activar / renovar licencia

```bash
# Solo en su PC (vendor), con el secreto configurado:
set KATIRE_LICENSE_SECRET=su-secreto-largo
python scripts/issue_license.py --shop "Autorespuesto" --expires 2028-07-21 --seats 8 --note "Renovacion"
```

Pegar la clave `KT1....` en la pantalla de login (Activar licencia) o en Render env `KATIRE_LICENSE_KEY`.

## Cobro recomendado (Costa Rica) — primer cliente

Para un taller con **patio + inventario con pistola + FE Hacienda**:

| Concepto | Monto sugerido | Notas |
|----------|----------------|-------|
| **Instalación / puesta en marcha** (una vez) | **₡75.000 – ₡120.000** (~$150–240) | Capacitación 1 día, carga de datos, identidad, primer croqui |
| **Mensualidad SaaS** | **₡55.000 – ₡70.000** (~$110–140) | Hosting, backups, soporte WA, actualizaciones |
| **Plan anual** (descuento) | **₡550.000 – ₡700.000** / año | ~2 meses de descuento |

**Recomendación para Autorespuesto (cliente 1 / vitrina):**  
- Cobrar **₡60.000/mes** + **₡90.000 de instalación** el primer mes.  
- O paquete lanzamiento: **primer mes ₡90.000** (incluye instalación) y luego **₡60.000/mes**.

Si el taller factura mucho con FE y varios usuarios, subir a **₡75.000/mes**.  
Si es solo patio sin FE aún: bajar a **₡45.000/mes** hasta activar Hacienda.

Incluya en el contrato: “Software Katire bajo licencia; prohibida la reventa a otros talleres.”

## Checklist entrega mañana

- [ ] Ctrl+F5 en https://katire.onrender.com — build con licencia  
- [ ] Login admin → se ve menú **Casa / Administración**  
- [ ] Login recepción → **no** ve Casa ni edita emisor/.p12  
- [ ] Abrir https://katire.onrender.com/docs → debe dar **404**  
- [ ] Patio con carro, Diagnóstico con croqui, Estantería con pistola  
- [ ] Cambiar clave del admin con el dueño presente  
- [ ] Firmar acuerdo de licencia (LICENSE.txt)  
- [ ] Definir fecha de cobro mensual (ej. día 1 o 5 de cada mes)  

## Soporte

WhatsApp vendor: +506 6370-6546  
Producto: Katire — De la llave al XML.
