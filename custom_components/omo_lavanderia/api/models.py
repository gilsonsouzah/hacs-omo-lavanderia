"""Data models for Omo Lavanderia API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MachineType(str, Enum):
    """Machine type enumeration."""

    WASHER = "WASHER"
    DRYER = "DRYER"


class MachineStatus(str, Enum):
    """Machine status enumeration."""

    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    RESERVED = "RESERVED"
    OFFLINE = "OFFLINE"


class UsageStatus(str, Enum):
    """Usage status enumeration."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class LaundryMachine:
    """Represents a laundry machine (washer or dryer)."""

    id: str
    code: str
    display_name: str
    type: MachineType
    status: MachineStatus
    status_fleet: str | None
    cycle_time: int  # in minutes
    price: float
    model: str | None
    serial: str | None
    load_type: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LaundryMachine:
        """Create a LaundryMachine from API response dictionary.

        Args:
            data: Dictionary containing machine data from API.

        Returns:
            LaundryMachine instance.
        """
        return cls(
            id=str(data.get("id", "")),
            code=data.get("code", ""),
            display_name=data.get("displayName", data.get("display_name", "")),
            type=MachineType(data.get("type", "WASHER")),
            status=MachineStatus(data.get("status", "OFFLINE")),
            status_fleet=data.get("statusFleet"),
            cycle_time=int(data.get("cycleTime", data.get("cycle_time", 0))),
            price=float(data.get("price", 0)),
            model=data.get("model"),
            serial=data.get("serial"),
            load_type=data.get("loadType", data.get("load_type")),
        )


@dataclass
class Coordinates:
    """Geographic coordinates."""

    latitude: float
    longitude: float

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Coordinates | None:
        """Create Coordinates from API response dictionary.

        Args:
            data: Dictionary containing coordinates data.

        Returns:
            Coordinates instance or None.
        """
        if not data:
            return None
        return cls(
            latitude=float(data.get("latitude", data.get("lat", 0))),
            longitude=float(data.get("longitude", data.get("lon", 0))),
        )


@dataclass
class Laundry:
    """Represents a laundry location."""

    id: str
    name: str
    code: str
    type: str
    coords: Coordinates | None
    timezone: str | None
    is_closed: bool
    is_blocked: bool
    payment_mode: str | None
    machines: list[LaundryMachine] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Laundry:
        """Create a Laundry from API response dictionary.

        Args:
            data: Dictionary containing laundry data from API.

        Returns:
            Laundry instance.
        """
        machines_data = data.get("machines", [])
        machines = [LaundryMachine.from_dict(m) for m in machines_data]

        coords_data = data.get("coords") or data.get("coordinates")

        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", ""),
            code=data.get("code", ""),
            type=data.get("type", ""),
            coords=Coordinates.from_dict(coords_data),
            timezone=data.get("timezone"),
            is_closed=bool(data.get("isClosed", data.get("is_closed", False))),
            is_blocked=bool(data.get("isBlocked", data.get("is_blocked", False))),
            payment_mode=data.get("paymentMode", data.get("payment_mode")),
            machines=machines,
        )


@dataclass
class OrderMachine:
    """Represents a machine in an active order."""

    machine_id: str
    machine_code: str
    machine_type: MachineType
    remaining_time: int  # in seconds
    usage_status: UsageStatus
    start_usage_at: datetime | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrderMachine:
        """Create an OrderMachine from API response dictionary.

        Args:
            data: Dictionary containing order machine data.

        Returns:
            OrderMachine instance.
        """
        start_usage_str = data.get("startUsageAt", data.get("start_usage_at"))
        start_usage_at = None
        if start_usage_str:
            try:
                start_usage_at = datetime.fromisoformat(
                    start_usage_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        return cls(
            machine_id=str(data.get("machineId", data.get("machine_id", ""))),
            machine_code=data.get("machineCode", data.get("machine_code", "")),
            machine_type=MachineType(data.get("machineType", data.get("type", "WASHER"))),
            remaining_time=int(data.get("remainingTime", data.get("remaining_time", 0))),
            usage_status=UsageStatus(
                data.get("usageStatus", data.get("usage_status", "PENDING"))
            ),
            start_usage_at=start_usage_at,
        )


@dataclass
class ActiveOrder:
    """Represents an active order."""

    id: str
    laundry_id: str
    total_price: float
    status: str
    machines: list[OrderMachine] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActiveOrder:
        """Create an ActiveOrder from API response dictionary.

        Args:
            data: Dictionary containing order data from API.

        Returns:
            ActiveOrder instance.
        """
        machines_data = data.get("machines", data.get("orderMachines", []))
        machines = [OrderMachine.from_dict(m) for m in machines_data]

        return cls(
            id=str(data.get("id", "")),
            laundry_id=str(data.get("laundryId", data.get("laundry_id", ""))),
            total_price=float(data.get("totalPrice", data.get("total_price", 0))),
            status=data.get("status", ""),
            machines=machines,
        )


@dataclass
class PaymentCard:
    """Represents a payment card."""

    id: str
    brand: str
    last_digits: str
    holder_name: str
    nickname: str | None
    is_active: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaymentCard:
        """Create a PaymentCard from API response dictionary.

        Args:
            data: Dictionary containing card data from API.

        Returns:
            PaymentCard instance.
        """
        return cls(
            id=str(data.get("id", "")),
            brand=data.get("brand", ""),
            last_digits=data.get("lastDigits", data.get("last_digits", "")),
            holder_name=data.get("holderName", data.get("holder_name", "")),
            nickname=data.get("nickname"),
            is_active=bool(data.get("isActive", data.get("is_active", True))),
        )


@dataclass
class UserInfo:
    """Represents user information."""

    email: str
    name: str
    document: str | None
    verified: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserInfo:
        """Create a UserInfo from API response dictionary.

        Args:
            data: Dictionary containing user data from API.

        Returns:
            UserInfo instance.
        """
        return cls(
            email=data.get("email", ""),
            name=data.get("name", ""),
            document=data.get("document"),
            verified=bool(data.get("verified", data.get("isVerified", False))),
        )
