import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class SeatAvailabilityConsumer(AsyncWebsocketConsumer):
    """
    WebSocket Consumer handling real-time seat availability updates for a given show.
    Endpoint: /ws/shows/<show_id>/seats/
    """
    async def connect(self):
        self.show_id = self.scope['url_route']['kwargs']['show_id']
        self.room_group_name = f'show_{self.show_id}_seats'

        try:
            if self.channel_layer:
                await self.channel_layer.group_add(
                    self.room_group_name,
                    self.channel_name
                )
        except Exception as e:
            logger.warning(f"WebSocket channel_layer group_add skipped safely: {e}")

        await self.accept()

        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'show_id': self.show_id,
            'message': f'Connected to real-time seat channel for Show #{self.show_id}'
        }))

    async def disconnect(self, close_code):
        try:
            if self.channel_layer:
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
        except Exception as e:
            logger.debug(f"WebSocket channel_layer group_discard skipped: {e}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except Exception as e:
            logger.warning(f"Error handling WebSocket message: {e}")

    async def seat_status_changed(self, event):
        """
        Broadcasts seat status updates (RESERVED, AVAILABLE, BOOKED) to clients.
        """
        await self.send(text_data=json.dumps({
            'type': 'seat_status_changed',
            'show_id': event['show_id'],
            'seats': event['seats'],
            'status': event['status'],
            'reserved_until': event.get('reserved_until')
        }))


def broadcast_seat_status_change(show_id, seats, status, reserved_until=None):
    """
    Synchronous helper to broadcast seat state updates over Channel layer.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'show_{show_id}_seats',
                {
                    'type': 'seat_status_changed',
                    'show_id': show_id,
                    'seats': seats,
                    'status': status,
                    'reserved_until': reserved_until
                }
            )
    except Exception as err:
        logger.warning(f"Failed to broadcast WebSocket seat event for Show #{show_id}: {err}")
