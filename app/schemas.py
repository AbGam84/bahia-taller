from datetime import datetime

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class CustomerIn(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    id_number: str = ""
    notes: str = ""


class VehicleIn(BaseModel):
    customer_id: int
    plate: str
    brand: str
    model: str
    year: int = 0
    color: str = ""
    vin: str = ""
    notes: str = ""


class DamageIn(BaseModel):
    zone: str
    severity: str = "leve"
    description: str = ""
    present_on_arrival: bool = True


class ReceptionIn(BaseModel):
    customer: CustomerIn | None = None
    customer_id: int | None = None
    vehicle: VehicleIn | None = None
    vehicle_id: int | None = None
    plate: str = ""
    brand: str = ""
    model: str = ""
    year: int = 0
    color: str = ""
    odometer_km: int = 0
    fuel_level: str = "1/2"
    customer_complaint: str = ""
    accessories: str = ""
    received_by: str = ""
    promised_hours: int = 24
    damages: list[DamageIn] = Field(default_factory=list)
    customer_accepted: bool = False
    customer_signature_name: str = ""


class DiagnosisIn(BaseModel):
    technician: str = ""
    symptoms: str = ""
    findings: str = ""
    obd_codes: str = ""
    recommended_work: str = ""
    estimated_hours: float = 0
    estimated_parts_cost: float = 0
    estimated_labor_cost: float = 0
    priority: str = "normal"
    create_work_order: bool = True


class WorkOrderLineIn(BaseModel):
    part_id: int | None = None
    description: str
    quantity: float = 1
    unit_price: float | None = None


class WorkOrderUpdate(BaseModel):
    status: str | None = None
    labor_notes: str | None = None
    labor_hours: float | None = None
    labor_rate: float | None = None
    assigned_to: str | None = None


class PartIn(BaseModel):
    sku: str
    name: str
    brand: str = ""
    category: str = "General"
    compatible_with: str = ""
    location: str = ""
    cost_price: float = 0
    sale_price: float = 0
    stock_qty: float = 0
    min_stock: float = 1
    unit: str = "und"
    preferred_supplier_id: int | None = None


class StockAdjustIn(BaseModel):
    quantity: float
    movement_type: str = "ajuste"
    note: str = ""


class SupplierIn(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    city: str = "Liberia"
    notes: str = ""
    kind: str = "tienda"  # tienda | aliado
    website: str = ""
    whatsapp: str = ""
    search_url: str = ""
    specialty: str = ""


class AllyJobIn(BaseModel):
    ally_id: int
    reception_id: int | None = None
    work_order_id: int | None = None
    plate: str = ""
    vehicle_info: str = ""
    job_type: str = "otro"
    description: str = ""
    cost_estimated: float = 0
    due_at: str | None = None  # ISO date


class AllyJobUpdateIn(BaseModel):
    status: str | None = None
    note: str = ""
    cost_final: float | None = None
    due_at: str | None = None


class PurchaseOrderIn(BaseModel):
    supplier_id: int
    work_order_id: int | None = None
    notes: str = ""
    lines: list[dict]


class StatusUpdate(BaseModel):
    status: str


class SettingsIn(BaseModel):
    shop_name: str | None = None
    slogan: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    address: str | None = None
    labor_rate: float | None = None
