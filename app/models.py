from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="mecanico")  # admin, recepcion, mecanico
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    id_number: Mapped[str] = mapped_column(String(60), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="customer")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    plate: Mapped[str] = mapped_column(String(20), index=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(80))
    year: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str] = mapped_column(String(40), default="")
    vin: Mapped[str] = mapped_column(String(60), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="vehicles")
    receptions: Mapped[list["Reception"]] = relationship(back_populates="vehicle")


class Reception(Base):
    __tablename__ = "receptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    received_by: Mapped[str] = mapped_column(String(120), default="")
    odometer_km: Mapped[int] = mapped_column(Integer, default=0)
    fuel_level: Mapped[str] = mapped_column(String(20), default="1/2")
    customer_complaint: Mapped[str] = mapped_column(Text, default="")
    accessories: Mapped[str] = mapped_column(Text, default="")  # JSON list as text
    status: Mapped[str] = mapped_column(String(40), default="recibido")
    # recibido | en_diagnostico | esperando_repuestos | en_reparacion | listo | entregado | cancelado
    promised_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    customer_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    customer_signature_name: Mapped[str] = mapped_column(String(160), default="")
    public_token: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="receptions")
    damages: Mapped[list["DamageItem"]] = relationship(back_populates="reception", cascade="all, delete-orphan")
    photos: Mapped[list["ReceptionPhoto"]] = relationship(back_populates="reception", cascade="all, delete-orphan")
    diagnosis: Mapped["Diagnosis | None"] = relationship(back_populates="reception", uselist=False)
    work_order: Mapped["WorkOrder | None"] = relationship(back_populates="reception", uselist=False)
    inspection_checks: Mapped[list["InspectionCheck"]] = relationship(
        back_populates="reception", cascade="all, delete-orphan"
    )
    estimate: Mapped["Estimate | None"] = relationship(back_populates="reception", uselist=False)


class DamageItem(Base):
    __tablename__ = "damage_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reception_id: Mapped[int] = mapped_column(ForeignKey("receptions.id"))
    zone: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20), default="leve")  # leve, medio, grave
    description: Mapped[str] = mapped_column(Text, default="")
    present_on_arrival: Mapped[bool] = mapped_column(Boolean, default=True)

    reception: Mapped["Reception"] = relationship(back_populates="damages")


class ReceptionPhoto(Base):
    __tablename__ = "reception_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reception_id: Mapped[int] = mapped_column(ForeignKey("receptions.id"))
    filename: Mapped[str] = mapped_column(String(255))
    caption: Mapped[str] = mapped_column(String(200), default="")
    zone: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    reception: Mapped["Reception"] = relationship(back_populates="photos")


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reception_id: Mapped[int] = mapped_column(ForeignKey("receptions.id"), unique=True)
    technician: Mapped[str] = mapped_column(String(120), default="")
    symptoms: Mapped[str] = mapped_column(Text, default="")
    findings: Mapped[str] = mapped_column(Text, default="")
    obd_codes: Mapped[str] = mapped_column(Text, default="")
    recommended_work: Mapped[str] = mapped_column(Text, default="")
    estimated_hours: Mapped[float] = mapped_column(Float, default=0)
    estimated_parts_cost: Mapped[float] = mapped_column(Float, default=0)
    estimated_labor_cost: Mapped[float] = mapped_column(Float, default=0)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    reception: Mapped["Reception"] = relationship(back_populates="diagnosis")


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reception_id: Mapped[int] = mapped_column(ForeignKey("receptions.id"), unique=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="abierta")
    labor_notes: Mapped[str] = mapped_column(Text, default="")
    labor_hours: Mapped[float] = mapped_column(Float, default=0)
    labor_rate: Mapped[float] = mapped_column(Float, default=15000)
    labor_total: Mapped[float] = mapped_column(Float, default=0)
    parts_total: Mapped[float] = mapped_column(Float, default=0)
    grand_total: Mapped[float] = mapped_column(Float, default=0)
    assigned_to: Mapped[str] = mapped_column(String(120), default="")
    payment_status: Mapped[str] = mapped_column(String(30), default="pendiente")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    reception: Mapped["Reception"] = relationship(back_populates="work_order")
    lines: Mapped[list["WorkOrderLine"]] = relationship(back_populates="work_order", cascade="all, delete-orphan")


class WorkOrderLine(Base):
    __tablename__ = "work_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"))
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="pendiente")
    # pendiente | reservado | pedido | instalado

    work_order: Mapped["WorkOrder"] = relationship(back_populates="lines")
    part: Mapped["Part | None"] = relationship()


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    city: Mapped[str] = mapped_column(String(80), default="Liberia")
    notes: Mapped[str] = mapped_column(Text, default="")
    # tienda = compra repuestos | aliado = envía trabajos (cajas, motores, etc.)
    kind: Mapped[str] = mapped_column(String(30), default="tienda")
    website: Mapped[str] = mapped_column(String(255), default="")
    whatsapp: Mapped[str] = mapped_column(String(40), default="")
    # URL con {q} para buscar el repuesto en su tienda
    search_url: Mapped[str] = mapped_column(String(400), default="")
    specialty: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    parts: Mapped[list["Part"]] = relationship(back_populates="preferred_supplier")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")
    ally_jobs: Mapped[list["AllyJob"]] = relationship(back_populates="ally")


class AllyJob(Base):
    """Trabajo enviado a un aliado: cajas, motores, radiadores, etc."""

    __tablename__ = "ally_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    ally_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    reception_id: Mapped[int | None] = mapped_column(ForeignKey("receptions.id"), nullable=True)
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    plate: Mapped[str] = mapped_column(String(20), default="")
    vehicle_info: Mapped[str] = mapped_column(String(200), default="")
    job_type: Mapped[str] = mapped_column(String(60), default="otro")
    # caja_cambios | motor | radiador | electrico | carroceria | inyeccion | otro
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="cotizado")
    # cotizado | enviado | en_proceso | listo | recibido | cancelado
    cost_estimated: Mapped[float] = mapped_column(Float, default=0)
    cost_final: Mapped[float] = mapped_column(Float, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    ally: Mapped["Supplier"] = relationship(back_populates="ally_jobs")
    events: Mapped[list["AllyJobEvent"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class AllyJobEvent(Base):
    __tablename__ = "ally_job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("ally_jobs.id"))
    status: Mapped[str] = mapped_column(String(40), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    job: Mapped["AllyJob"] = relationship(back_populates="events")


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(80), default="")
    category: Mapped[str] = mapped_column(String(80), default="General")
    compatible_with: Mapped[str] = mapped_column(Text, default="")  # marcas/modelos
    location: Mapped[str] = mapped_column(String(60), default="")  # pasillo/estante
    cost_price: Mapped[float] = mapped_column(Float, default=0)
    sale_price: Mapped[float] = mapped_column(Float, default=0)
    stock_qty: Mapped[float] = mapped_column(Float, default=0)
    min_stock: Mapped[float] = mapped_column(Float, default=1)
    unit: Mapped[str] = mapped_column(String(20), default="und")
    preferred_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    preferred_supplier: Mapped["Supplier | None"] = relationship(back_populates="parts")
    movements: Mapped[list["StockMovement"]] = relationship(back_populates="part")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"))
    movement_type: Mapped[str] = mapped_column(String(30))  # entrada, salida, ajuste, reserva, liberacion
    quantity: Mapped[float] = mapped_column(Float)
    reference: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(120), default="")

    part: Mapped["Part"] = relationship(back_populates="movements")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="solicitado")
    # solicitado | confirmado | en_camino | recibido | cancelado
    notes: Mapped[str] = mapped_column(Text, default="")
    total: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"))
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")
    part: Mapped["Part"] = relationship()


class ShopSettings(Base):
    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_name: Mapped[str] = mapped_column(String(160), default="Katire")
    slogan: Mapped[str] = mapped_column(String(200), default="De la llave al XML.")
    phone: Mapped[str] = mapped_column(String(40), default="")
    whatsapp: Mapped[str] = mapped_column(String(40), default="")
    address: Mapped[str] = mapped_column(String(255), default="Guanacaste, Costa Rica")
    labor_rate: Mapped[float] = mapped_column(Float, default=15000)
    currency: Mapped[str] = mapped_column(String(10), default="CRC")


class InspectionCheck(Base):
    """Digital Vehicle Inspection item — Tekmetric/Shopmonkey style traffic light."""

    __tablename__ = "inspection_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reception_id: Mapped[int] = mapped_column(ForeignKey("receptions.id"))
    system_key: Mapped[str] = mapped_column(String(40))
    system_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | watch | fail | na
    notes: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    reception: Mapped["Reception"] = relationship(back_populates="inspection_checks")


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reception_id: Mapped[int] = mapped_column(ForeignKey("receptions.id"), unique=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="borrador")
    # borrador | enviada | aprobada | rechazada
    notes: Mapped[str] = mapped_column(Text, default="")
    labor_total: Mapped[float] = mapped_column(Float, default=0)
    parts_total: Mapped[float] = mapped_column(Float, default=0)
    grand_total: Mapped[float] = mapped_column(Float, default=0)
    customer_message: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    reception: Mapped["Reception"] = relationship(back_populates="estimate")
    lines: Mapped[list["EstimateLine"]] = relationship(
        back_populates="estimate", cascade="all, delete-orphan"
    )


class EstimateLine(Base):
    __tablename__ = "estimate_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"))
    kind: Mapped[str] = mapped_column(String(20), default="servicio")  # servicio | repuesto
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id"), nullable=True)
    recommended: Mapped[bool] = mapped_column(Boolean, default=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

    estimate: Mapped["Estimate"] = relationship(back_populates="lines")


class ServiceCatalog(Base):
    __tablename__ = "service_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80), default="General")
    hours: Mapped[float] = mapped_column(Float, default=1)
    price: Mapped[float] = mapped_column(Float, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40), default="")
    plate: Mapped[str] = mapped_column(String(20), default="")
    vehicle_info: Mapped[str] = mapped_column(String(160), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), default="agendada")
    # agendada | confirmada | llegada | cancelada | no_show
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IssuerProfile(Base):
    """Datos del emisor ante Hacienda / ATV."""

    __tablename__ = "issuer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), default="")
    nombre_comercial: Mapped[str] = mapped_column(String(200), default="")
    tipo_id: Mapped[str] = mapped_column(String(2), default="02")
    numero_id: Mapped[str] = mapped_column(String(20), default="")
    codigo_actividad: Mapped[str] = mapped_column(String(10), default="")
    correo: Mapped[str] = mapped_column(String(160), default="")
    telefono: Mapped[str] = mapped_column(String(40), default="")
    provincia: Mapped[str] = mapped_column(String(2), default="5")
    canton: Mapped[str] = mapped_column(String(2), default="01")
    distrito: Mapped[str] = mapped_column(String(2), default="01")
    otras_senas: Mapped[str] = mapped_column(String(255), default="")
    sucursal: Mapped[str] = mapped_column(String(3), default="001")
    terminal: Mapped[str] = mapped_column(String(5), default="00001")
    ambiente: Mapped[str] = mapped_column(String(20), default="sandbox")  # sandbox | production
    hacienda_user: Mapped[str] = mapped_column(String(160), default="")
    hacienda_password: Mapped[str] = mapped_column(String(255), default="")
    pin_cert: Mapped[str] = mapped_column(String(120), default="")
    cert_filename: Mapped[str] = mapped_column(String(255), default="")
    cabys_default_servicio: Mapped[str] = mapped_column(String(20), default="8314100000000")
    cabys_default_repuesto: Mapped[str] = mapped_column(String(20), default="4530000000000")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class InvoiceSequence(Base):
    __tablename__ = "invoice_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(2), index=True)
    sucursal: Mapped[str] = mapped_column(String(3), default="001")
    terminal: Mapped[str] = mapped_column(String(5), default="00001")
    last_number: Mapped[int] = mapped_column(Integer, default=0)


class ElectronicInvoice(Base):
    __tablename__ = "electronic_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clave: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    numero_consecutivo: Mapped[str] = mapped_column(String(20), index=True)
    tipo_documento: Mapped[str] = mapped_column(String(2), default="01")
    status: Mapped[str] = mapped_column(String(40), default="borrador")
    # borrador | xml_listo | enviado | aceptado | rechazado | error
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    reception_id: Mapped[int | None] = mapped_column(ForeignKey("receptions.id"), nullable=True)
    receptor_nombre: Mapped[str] = mapped_column(String(200), default="")
    receptor_tipo_id: Mapped[str] = mapped_column(String(2), default="01")
    receptor_numero_id: Mapped[str] = mapped_column(String(20), default="")
    receptor_correo: Mapped[str] = mapped_column(String(160), default="")
    condicion_venta: Mapped[str] = mapped_column(String(2), default="01")
    medio_pago: Mapped[str] = mapped_column(String(40), default="01")
    moneda: Mapped[str] = mapped_column(String(3), default="CRC")
    total_venta: Mapped[float] = mapped_column(Float, default=0)
    total_impuesto: Mapped[float] = mapped_column(Float, default=0)
    total_comprobante: Mapped[float] = mapped_column(Float, default=0)
    xml_content: Mapped[str] = mapped_column(Text, default="")
    hacienda_response: Mapped[str] = mapped_column(Text, default="")
    hacienda_status: Mapped[str] = mapped_column(String(80), default="")
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    lines: Mapped[list["ElectronicInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class ElectronicInvoiceLine(Base):
    __tablename__ = "electronic_invoice_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("electronic_invoices.id"))
    detalle: Mapped[str] = mapped_column(String(255))
    cabys: Mapped[str] = mapped_column(String(20), default="")
    cantidad: Mapped[float] = mapped_column(Float, default=1)
    unidad: Mapped[str] = mapped_column(String(20), default="Sp")
    precio_unitario: Mapped[float] = mapped_column(Float, default=0)
    monto_descuento: Mapped[float] = mapped_column(Float, default=0)
    tarifa_codigo: Mapped[str] = mapped_column(String(2), default="08")
    tarifa: Mapped[float] = mapped_column(Float, default=13)
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    impuesto_monto: Mapped[float] = mapped_column(Float, default=0)
    monto_total_linea: Mapped[float] = mapped_column(Float, default=0)
    es_servicio: Mapped[bool] = mapped_column(Boolean, default=True)

    invoice: Mapped["ElectronicInvoice"] = relationship(back_populates="lines")
