"""Tests for Omo Lavanderia API models."""
import pytest

from custom_components.omo_lavanderia.api.models import (
    ActiveOrder,
    ActiveOrderMachine,
    Laundry,
    LaundryMachine,
    MachineStatus,
    MachineType,
    PaymentCard,
)


class TestLaundryMachine:
    """Tests for LaundryMachine model."""

    def test_from_dict_washer(self):
        """Test creating washer from API response."""
        data = {
            "id": "6fd27ed3-231e-4f07-9e34-0dcf3dfe3f21",
            "code": "mac_2a6931",
            "displayName": "L1",
            "laundryId": "d944decd-ef93-440e-afd3-0d7212bc1eb4",
            "type": "WASHER",
            "serial": "2310030869",
            "model": "STENXASP543DW01",
            "cycleTime": 30,
            "status": "AVAILABLE",
            "price": {"price": 10.28, "service": "43d76629-8f5e-4118-bb0a-49dfcac39de4"},
            "unavailable": None,
        }

        machine = LaundryMachine.from_dict(data)

        assert machine.id == "6fd27ed3-231e-4f07-9e34-0dcf3dfe3f21"
        assert machine.display_name == "L1"
        assert machine.machine_type == MachineType.WASHER
        assert machine.status == MachineStatus.AVAILABLE
        assert machine.cycle_time == 30
        assert machine.price.price == 10.28
        assert machine.unavailable is None

    def test_from_dict_dryer_in_use(self):
        """Test creating dryer in use from API response."""
        data = {
            "id": "bb72763a-9fa7-4103-aef7-37c7627e5741",
            "code": "mac_1d107e",
            "displayName": "S1",
            "laundryId": "d944decd-ef93-440e-afd3-0d7212bc1eb4",
            "type": "DRYER",
            "serial": "2310030869",
            "model": "STENXASP543DW01",
            "cycleTime": 45,
            "status": "IN_USE",
            "price": {"price": 10.28, "service": "34eba87f-8026-4fe5-908e-e647d7e0ba02"},
            "unavailable": {"reason": "IN_USE", "timeLeft": 11},
        }

        machine = LaundryMachine.from_dict(data)

        assert machine.display_name == "S1"
        assert machine.machine_type == MachineType.DRYER
        assert machine.status == MachineStatus.IN_USE
        assert machine.cycle_time == 45
        assert machine.unavailable is not None
        assert machine.unavailable.reason == "IN_USE"
        assert machine.unavailable.time_left == 11


class TestLaundry:
    """Tests for Laundry model."""

    def test_from_list_item(self):
        """Test creating laundry from paginated list item."""
        data = {
            "id": "d944decd-ef93-440e-afd3-0d7212bc1eb4",
            "name": "536555243 - CONDOMINIO ALTANO LAGO DOS PATOS",
            "code": "p85bid",
            "type": "OLC",
            "isClosed": False,
            "isBlocked": False,
        }

        laundry = Laundry.from_list_item(data)

        assert laundry.id == "d944decd-ef93-440e-afd3-0d7212bc1eb4"
        assert laundry.name == "536555243 - CONDOMINIO ALTANO LAGO DOS PATOS"
        assert laundry.laundry_type == "OLC"
        assert laundry.is_closed is False
        assert laundry.is_blocked is False

    def test_from_detail(self):
        """Test creating laundry from detail response."""
        data = {
            "id": "d944decd-ef93-440e-afd3-0d7212bc1eb4",
            "name": "536555243 - CONDOMINIO ALTANO LAGO DOS PATOS",
            "code": "p85bid",
            "type": "OLC",
            "paymentMode": "PREPAID",
            "isClosed": False,
            "isBlocked": False,
            "laundryAddress": {
                "street": "RUA RIO GRANDE",
                "number": 375,
                "neighborhood": "VILA ROSÁLIA",
                "city": "GUARULHOS",
            },
            "machines": {
                "washers": [
                    {
                        "id": "6fd27ed3-231e-4f07-9e34-0dcf3dfe3f21",
                        "displayName": "L1",
                        "type": "WASHER",
                        "status": "AVAILABLE",
                        "cycleTime": 30,
                    }
                ],
                "dryers": [
                    {
                        "id": "bb72763a-9fa7-4103-aef7-37c7627e5741",
                        "displayName": "S1",
                        "type": "DRYER",
                        "status": "IN_USE",
                        "cycleTime": 45,
                    }
                ],
            },
        }

        laundry = Laundry.from_detail(data)

        assert laundry.id == "d944decd-ef93-440e-afd3-0d7212bc1eb4"
        assert laundry.payment_mode == "PREPAID"
        assert len(laundry.washers) == 1
        assert len(laundry.dryers) == 1
        assert laundry.washers[0].display_name == "L1"
        assert laundry.dryers[0].display_name == "S1"
        assert laundry.address is not None
        assert laundry.address.city == "GUARULHOS"


class TestActiveOrder:
    """Tests for ActiveOrder model."""

    def test_from_dict(self):
        """Test creating active order from API response."""
        data = {
            "id": "5cd55c33-0afe-4c21-95d3-6aaa585f86ab",
            "laundryId": "d944decd-ef93-440e-afd3-0d7212bc1eb4",
            "laundryName": "536555243 - CONDOMINIO ALTANO LAGO DOS PATOS",
            "totalPrice": 10.28,
            "status": "IN_PROGRESS",
            "machines": [
                {
                    "id": "0e25b055-112a-4246-b085-23f5f2ac9234",
                    "type": "DRYER",
                    "status": "IN_PROGRESS",
                    "remainingTime": 619,
                    "usageStatus": "IN_USE",
                    "displayName": "S1",
                }
            ],
        }

        order = ActiveOrder.from_dict(data)

        assert order.id == "5cd55c33-0afe-4c21-95d3-6aaa585f86ab"
        assert order.laundry_id == "d944decd-ef93-440e-afd3-0d7212bc1eb4"
        assert order.total_price == 10.28
        assert order.status == "IN_PROGRESS"
        assert len(order.machines) == 1
        assert order.machines[0].display_name == "S1"
        assert order.machines[0].remaining_time == 619
        assert order.machines[0].machine_type == MachineType.DRYER


class TestPaymentCard:
    """Tests for PaymentCard model."""

    def test_from_dict(self):
        """Test creating payment card from API response."""
        data = {
            "id": "2fce3889-2aea-45af-9bba-34f294cef0f8",
            "nickname": "Porto Gilson",
            "holderName": "Gilson F B Souza",
            "lastFour": "8218",
            "brand": "visa",
        }

        card = PaymentCard.from_dict(data)

        assert card.id == "2fce3889-2aea-45af-9bba-34f294cef0f8"
        assert card.nickname == "Porto Gilson"
        assert card.holder_name == "Gilson F B Souza"
        assert card.last_four == "8218"
        assert card.brand == "visa"

    def test_display_name(self):
        """Test card display name property."""
        card = PaymentCard(
            id="123",
            nickname="My Card",
            holder_name="Test User",
            last_four="1234",
            brand="mastercard",
        )

        assert card.display_name == "My Card (mastercard ****1234)"
