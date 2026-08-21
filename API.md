# 📑 CinePass REST API Documentation

Comprehensive API documentation for CinePass Movie Discovery & Ticket Booking Platform.

---

## 1. System Health Check
- **Endpoint**: `GET /api/health/`
- **Auth**: None
- **Response**:
  ```json
  {
      "status": "ok",
      "database": "ok",
      "version": "1.0.0"
  }
  ```

---

## 2. Movie Discovery & Search
- **Endpoint**: `GET /api/movies/`
- **Parameters**:
  - `search` (or `q`): Search query across title, plot, director
  - `genre`: Filter by genre ID / slug / name
  - `language`: Filter by language ISO code / name
  - `city`: Filter by city ID / name
  - `rating_min`: Minimum rating (1-10)
  - `sort`: `popularity`, `newest`, `rating`, `price_low`, `price_high`
  - `page`: Page number (default: 1)
- **Response**:
  ```json
  {
      "count": 120,
      "page": 1,
      "total_pages": 12,
      "next": 2,
      "previous": null,
      "results": [
          {
              "id": 1,
              "title": "Dune: Part Two",
              "rating": 8.6,
              "poster_url": "https://image.tmdb.org/...",
              "genres": ["Sci-Fi", "Adventure"]
          }
      ]
  }
  ```

---

## 3. Real-Time Seat Availability
- **Endpoint**: `GET /shows/<show_id>/api/seats/`
- **Auth**: Optional
- **Response**:
  ```json
  {
      "success": true,
      "show_id": 4,
      "base_price": 250.0,
      "seats": [
          {
              "id": 101,
              "row": "A",
              "number": 1,
              "seat_type": "REGULAR",
              "price": 250.0,
              "status": "AVAILABLE"
          }
      ]
  }
  ```

---

## 4. Atomic 2-Minute Seat Reservation
- **Endpoint**: `POST /shows/<show_id>/api/reserve/`
- **Auth**: Required
- **Body**: `{"seat_ids": [101, 102]}`
- **Response (200 OK)**:
  ```json
  {
      "success": true,
      "message": "Seats successfully reserved for 2 minutes.",
      "countdown_seconds": 120,
      "total_price": 500.0,
      "grand_total": 530.0
  }
  ```

---

## 5. Razorpay Signature Verification & Booking Confirmation
- **Endpoint**: `POST /payments/verify/`
- **Auth**: Required
- **Body**:
  ```json
  {
      "razorpay_order_id": "order_L98x2Z",
      "razorpay_payment_id": "pay_P98x2Z",
      "razorpay_signature": "a1b2c3d4...",
      "booking_id": 42
  }
  ```
- **Response**:
  ```json
  {
      "success": true,
      "message": "Payment verified and booking confirmed!",
      "booking_number": "CP-8X92K4"
  }
  ```

---

## 6. QR Code Ticket Verification
- **Endpoint**: `GET /api/tickets/verify/<token>/`
- **Auth**: Public
- **Headers**: `Accept: application/json`
- **Response**:
  ```json
  {
      "status": "VALID",
      "booking_number": "CP-8X92K4",
      "movie": "Dune: Part Two",
      "theater": "PVR Cineplex Hyderabad",
      "show_time": "2026-08-10T18:00:00+05:30",
      "seats": 2
  }
  ```
