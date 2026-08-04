# Content Management System API

## Authentication
All endpoints require Bearer token from `/api/login`.

## Endpoints

### GET /api/recommendations
Fetch personalized recommendations for the logged-in user.

**Parameters:**
- `num` (int, default=5): Number of recommendations

**Response:**
```json
[
  {
    "id": "card-id",
    "type": "knowledge_card",
    "data": { "title": "...", "body": "..." },
    "reason": "You need practice in this topic",
    "reason_topic": "fund"
  }
]
```

### GET /api/admin/contents
List all contents (admin only).

**Parameters:**
- `type` (string, optional): Filter by content type (knowledge_card, quiz, term, article)

**Response:**
```json
[
  {
    "id": "content-id",
    "type": "knowledge_card",
    "data": { ... },
    "created_by": "admin",
    "created_at": "2026-08-04T10:00:00",
    "updated_at": "2026-08-04T10:00:00"
  }
]
```

### POST /api/admin/contents
Create new content (admin only).

**Request:**
```json
{
  "type": "knowledge_card",
  "data": {
    "title": "What is a Fund?",
    "body": "...",
    "difficulty": "L1",
    "topics": ["fund"],
    "quizIds": []
  }
}
```

**Response:** 201 Created
```json
{
  "id": "new-content-id",
  "type": "knowledge_card"
}
```

### PUT /api/admin/contents/{id}
Update existing content (admin only).

### DELETE /api/admin/contents/{id}
Delete content (admin only).

### GET /api/admin/contents/{id}/versions
Get version history for a content item (admin only).

**Response:**
```json
[
  {
    "id": "version-id",
    "changed_by": "admin",
    "changed_at": "2026-08-04T10:00:00",
    "action": "create|update|delete",
    "diff": { ... }
  }
]
```

## Error Responses

- 401 Unauthorized: Missing or invalid token
- 403 Forbidden: Not admin
- 400 Bad Request: Invalid input
- 500 Internal Server Error: Server error
