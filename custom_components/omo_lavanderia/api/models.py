"""Data models for Omo Lavanderia API."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MachineType(Enum):
    """Machine type enum."""

    WASHER = "WASHER"
    DRYER = "DRYER"


class MachineStatus(Enum):
    """Machine status enum."""

    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    UNAVAILABLE = "UNAVAILABLE"
    OFFLINE = "OFFLINE"


@dataclass
class MachinePrice:
    """Machine price info."""

    price: float
    service_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MachinePrice:
        """Create from API response."""
        return cls(
            price=float(data.get("price", 0)),
            service_id=data.get("service", ""),
        )


@dataclass
class MachineUnavailable:
    """Machine unavailable info."""

    reason: str
    time_left: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MachineUnavailable | None:
        """Create from API response."""
        if data is None:
            return None
        return cls(
            reason=data.get("reason", ""),
            time_left=data.get("timeLeft"),
        )


@dataclass
class LaundryMachine:
    """Represents a laundry machine."""

    id: str
    code: str
    display_name: str
    laundry_id: str
    machine_type: MachineType
    serial: str
    model: str
    cycle_time: int  # in minutes
    status: MachineStatus
    price: MachinePrice | None = None
    unavailable: MachineUnavailable | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LaundryMachine:
        """Create from API response."""
        return cls(
            id=data.get("id", ""),
            code=data.get("code", ""),
            display_name=data.get("displayName", ""),
            laundry_id=data.get("laundryId", ""),
            machine_type=MachineType(data.get("type", "WASHER")),
            serial=data.get("serial", ""),
            model=data.get("model", ""),
            cycle_time=data.get("cycleTime", 30),
            status=MachineStatus(data.get("status", "AVAILABLE")),
            price=MachinePrice.from_dict(data["price"]) if data.get("price") else None,
            unavailable=MachineUnavailable.from_dict(data.get("unavailable")),
        )


@dataclass
class LaundryAddress:
    """Laundry address."""

    street: str
    number: int
    neighborhood: str
    city: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LaundryAddress:
        """Create from API response."""
        return cls(
            street=data.get("street", ""),
            number=data.get("number", 0),
            neighborhood=data.get("neighborhood", ""),
            city=data.get("city", ""),
        )


@dataclass
class Laundry:
    """Represents a laundry location."""

    id: str
    name: str
    code: str
    laundry_type: str
    is_closed: bool
    is_blocked: bool
    payment_mode: str = "PREPAID"
    address: LaundryAddress | None = None
    washers: list[LaundryMachine] = field(default_factory=list)
    dryers: list[LaundryMachine] = field(default_factory=list)

    @classmethod
    def from_list_item(cls, data: dict[str, Any]) -> Laundry:
        """Create from paginated list item."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            code=data.get("code", ""),
            laundry_type=data.get("type", ""),
            is_closed=data.get("isClosed", False),
            is_blocked=data.get("isBlocked", False),
        )

    @classmethod
    def from_detail(cls, data: dict[str, Any]) -> Laundry:
        """Create from laundry detail response."""
        machines = data.get("machines", {})
        washers = [LaundryMachine.from_dict(m) for m in machines.get("washers", [])]
        dryers = [LaundryMachine.from_dict(m) for m in machines.get("dryers", [])]

        address = None
        if data.get("laundryAddress"):
            address = LaundryAddress.from_dict(data["laundryAddress"])

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            code=data.get("code", ""),
            laundry_type=data.get("type", ""),
            is_closed=data.get("isClosed", False),
            is_blocked=data.get("isBlocked", False),
            payment_mode=data.get("paymentMode", "PREPAID"),
            address=address,
            washers=washers,
            dryers=dryers,
        )


@dataclass
class ActiveOrderMachine:
    """Machine in an active order."""

    id: str
    machine_type: MachineType
    status: str
    remaining_time: int  # in seconds
    usage_status: str
    display_name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActiveOrderMachine:
        """Create from API response."""
        return cls(
            id=data.get("id", ""),
            machine_type=MachineType(data.get("type", "WASHER")),
            status=data.get("status", ""),
            remaining_time=data.get("remainingTime", 0),
            usage_status=data.get("usageStatus", ""),
            display_name=data.get("displayName", ""),
        )


@dataclass
class ActiveOrder:
    """Represents an active order."""

    id: str
    laundry_id: str
    laundry_name: str
    total_price: float
    status: str
    machines: list[ActiveOrderMachine]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActiveOrder:
        """Create from API response."""
        machines = [
            ActiveOrderMachine.from_dict(m) for m in data.get("machines", [])
        ]
        return cls(
            id=data.get("id", ""),
            laundry_id=data.get("laundryId", ""),
            laundry_name=data.get("laundryName", ""),
            total_price=float(data.get("totalPrice", 0)),
            status=data.get("status", ""),
            machines=machines,
        )


@dataclass
class PaymentCard:
    """Represents a payment card."""

    id: str
    nickname: str
    holder_name: str
    last_four: str
    brand: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaymentCard:
        """Create from API response."""
        return cls(
            id=data.get("id", ""),
            nickname=data.get("nickname", ""),
            holder_name=data.get("holderName", ""),
            last_four=data.get("lastFour", ""),
            brand=data.get("brand", ""),
        )

    @property
    def display_name(self) -> str:
        """Get display name for the card."""
        return f"{self.nickname} ({self.brand} ****{self.last_four})"
