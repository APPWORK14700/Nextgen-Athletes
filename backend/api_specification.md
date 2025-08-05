# API Specification: Athlete Scouting App

## 1. Introduction

This document provides the API specification for the Athlete Scouting App. It details the available endpoints, request/response formats, authentication mechanisms, and error handling. The API is designed to be RESTful and follows standard conventions.

**Base URL:** `/api/v1`
**Authentication:** All endpoints (unless specified otherwise) require JWT-based authentication. The token must be passed in the `Authorization` header: `Authorization: Bearer <jwt-token>`.

**Rate Limiting:** All endpoints are rate-limited. Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit resets (Unix timestamp)

---

## 2. Non-Functional Requirements Compliance

- **Performance:** All `GET` endpoints that return a list of resources support pagination via `limit` and `offset` query parameters to ensure fast response times. AI analysis is performed asynchronously in the background to avoid blocking user interactions.
- **Security:**
    - Role-based access control (RBAC) is enforced on all endpoints. The required role (Athlete, Scout, Admin) is specified for each endpoint.
    - All data is exchanged over HTTPS (enforced at the infrastructure level).
    - Input validation is performed on all incoming data to prevent common vulnerabilities.
- **Scalability:** The API is designed to be stateless, allowing for horizontal scaling of backend services.
- **Usability:** The API follows a consistent and predictable structure. A standardized error response format is used across all endpoints.
- **Rate Limiting:** API requests are rate-limited to prevent abuse. Limits are applied per user and per endpoint.
- **API Versioning:** The API supports versioning through URL path (`/api/v1/`). Breaking changes will be introduced in new versions.
  - Version deprecation: Old versions will be supported for at least 12 months after deprecation notice
  - Migration guides will be provided for breaking changes
  - API version is also included in response headers: `X-API-Version: v1`

---

## 3. Data Models

### User
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "email_verified": "boolean",
  "role": "athlete" | "scout",
  "status": "active" | "suspended" | "deleted",
  "created_at": "timestamp"
}
```

### User Profile
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "username": "string",
  "phone_number": "string" (optional),
  "is_verified": "boolean",
  "is_active": "boolean",
  "last_login": "timestamp",
  "profile_completion": "integer" (0-100),
  "settings": {
    "notifications_enabled": "boolean",
    "privacy_level": "public" | "private" | "friends_only"
  }
}
```

### Stats/Achievements
```json
{
  "id": "uuid",
  "athlete_id": "uuid",
  "sport_category_id": "uuid",
  "season": "string",
  "team_name": "string" (optional),
  "league": "string" (optional),
  "position": "string" (optional),
  "stats": "object" (dynamic based on sport category stats_fields),
  "achievements": [
    {
      "type": "string" (achievement type key),
      "title": "string",
      "description": "string",
      "date_achieved": "date",
      "evidence_url": "url" (optional)
    }
  ],
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Organization
```json
{
  "id": "uuid",
  "name": "string",
  "type": "club" | "school" | "university" | "agency" | "other",
  "location": "string",
  "website": "url" (optional),
  "description": "string",
  "logo_url": "url" (optional),
  "is_verified": "boolean",
  "created_at": "timestamp"
}
```

### Athlete Profile
```json
{
  "user_id": "uuid",
  "first_name": "string",
  "last_name": "string",
  "date_of_birth": "date",
  "gender": "male" | "female" | "other",
  "location": "string",
  "primary_sport_category_id": "uuid",
  "secondary_sport_category_ids": ["uuid"] (optional),
  "position": "string",
  "height_cm": "integer",
  "weight_kg": "integer",
  "academic_info": "string",
  "career_highlights": "string",
  "profile_image_url": "url"
}
```

### Scout Profile
```json
{
    "user_id": "uuid",
    "first_name": "string",
    "last_name": "string",
    "organization": "string",
    "title": "string",
    "verification_status": "pending" | "verified" | "rejected",
    "focus_areas": ["U18 Soccer", "West Coast"]
}
```

### Media
```json
{
    "id": "uuid",
    "athlete_id": "uuid",
    "type": "video" | "image" | "reel",
    "url": "url",
    "thumbnail_url": "url",
    "created_at": "timestamp",
    "moderation_status": "pending" | "approved" | "rejected",
    "ai_analysis": {
        "status": "pending" | "processing" | "completed" | "failed" | "retrying",
        "rating": "exceptional" | "excellent" | "good" | "developing" | "needs_improvement" | null,
        "summary": "string" | null,
        "detailed_analysis": {
            "technical_skills": "float" (0-10),
            "physical_attributes": "float" (0-10),
            "game_intelligence": "float" (0-10),
            "consistency": "float" (0-10),
            "potential": "float" (0-10)
        } | null,
        "sport_specific_metrics": "object" | null,
        "confidence_score": "float" (0-1) | null,
        "analysis_started_at": "timestamp" | null,
        "analysis_completed_at": "timestamp" | null,
        "retry_count": "integer",
        "max_retries": "integer",
        "next_retry_at": "timestamp" | null,
        "error_message": "string" | null
    }
}
```

### Opportunity
```json
{
    "id": "uuid",
    "scout_id": "uuid",
    "title": "string",
    "description": "string",
    "type": "trial" | "scholarship" | "contract",
    "sport_category_id": "uuid",
    "location": "string",
    "start_date": "date",
    "end_date": "date" (optional),
    "requirements": "string" (optional),
    "compensation": "string" (optional),
    "is_active": "boolean",
    "moderation_status": "pending" | "approved" | "rejected",
    "created_at": "timestamp"
}
```

### Conversation
```json
{
    "id": "uuid",
    "participants": ["uuid"],
    "is_archived": "boolean",
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "last_message": "Message" object (optional)
}
```

### Message
```json
{
    "id": "uuid",
    "conversation_id": "uuid",
    "sender_id": "uuid",
    "content": "string",
    "attachment_url": "url" (optional),
    "is_read": "boolean",
    "created_at": "timestamp"
}
```

### Application
```json
{
    "id": "uuid",
    "opportunity_id": "uuid",
    "athlete_id": "uuid",
    "status": "pending" | "accepted" | "rejected" | "withdrawn",
    "cover_letter": "string" (optional),
    "resume_url": "url" (optional),
    "applied_at": "timestamp",
    "updated_at": "timestamp",
    "status_updated_at": "timestamp"
}
```

### Flag
```json
{
    "id": "uuid",
    "content_id": "uuid",
    "content_type": "media" | "opportunity" | "profile",
    "reporter_id": "uuid",
    "reason": "inappropriate_content" | "fake_profile" | "spam" | "harassment" | "copyright" | "other",
    "description": "string" (optional),
    "evidence_url": "url" (optional),
    "status": "pending" | "resolved" | "dismissed",
    "created_at": "timestamp",
    "resolved_at": "timestamp" (optional)
}
```

### Notification
```json
{
    "id": "uuid",
    "user_id": "uuid",
    "type": "message" | "opportunity" | "application" | "verification" | "moderation",
    "title": "string",
    "message": "string",
    "data": "object" (optional, additional context),
    "is_read": "boolean",
    "created_at": "timestamp"
}
```

### Search History
```json
{
    "id": "uuid",
    "user_id": "uuid",
    "search_type": "athletes" | "scouts" | "opportunities",
    "query": "string",
    "filters": "object",
    "created_at": "timestamp"
}
```

### Blocked User
```json
{
    "id": "uuid",
    "user_id": "uuid",
    "blocked_user_id": "uuid",
    "reason": "string" (optional),
    "created_at": "timestamp"
}
```

### Verification Document
```json
{
    "id": "uuid",
    "user_id": "uuid",
    "document_type": "id_card" | "passport" | "school_id" | "other",
    "document_url": "url",
    "status": "pending" | "approved" | "rejected",
    "additional_info": "string" (optional),
    "reviewed_by": "uuid" (optional),
    "reviewed_at": "timestamp" (optional),
    "created_at": "timestamp"
}
```

### User Report
```json
{
    "id": "uuid",
    "reporter_id": "uuid",
    "reported_user_id": "uuid",
    "reason": "harassment" | "spam" | "fake_profile" | "inappropriate_content" | "other",
    "description": "string",
    "evidence_url": "url" (optional),
    "status": "pending" | "resolved" | "dismissed",
    "resolved_by": "uuid" (optional),
    "resolved_at": "timestamp" (optional),
    "created_at": "timestamp"
}
```

### Sport Category
```json
{
    "id": "uuid",
    "name": "string",
    "description": "string",
    "icon_url": "url" (optional),
    "is_active": "boolean",
    "created_by": "uuid" (admin who created it),
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "stats_fields": [
        {
            "key": "string",
            "label": "string",
            "type": "integer" | "float" | "string" | "boolean",
            "unit": "string" (optional, e.g., "meters", "seconds", "goals"),
            "required": "boolean",
            "default_value": "any" (optional),
            "validation": {
                "min": "number" (optional),
                "max": "number" (optional),
                "pattern": "string" (optional, regex pattern)
            },
            "display_order": "integer"
        }
    ],
    "achievement_types": [
        {
            "key": "string",
            "label": "string",
            "description": "string",
            "icon_url": "url" (optional)
        }
    ]
}
```

---

## 4. API Endpoints

### 4.1. Authentication

#### `POST /auth/register`
- **Description:** Registers a new user.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword",
    "role": "athlete" | "scout",
    // Profile information is collected in a separate step after registration
    "first_name": "string",
    "last_name": "string"
  }
  ```
- **Response (201):**
  ```json
  {
    "user_id": "uuid",
    "email": "user@example.com",
    "access_token": "jwt-token"
  }
  ```

#### `POST /auth/login`
- **Description:** Authenticates a user and returns a JWT.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword"
  }
  ```
- **Response (200):**
  ```json
  {
    "access_token": "jwt-token",
    "token_type": "bearer"
  }
  ```

#### `POST /auth/verify-email`
- **Description:** Verifies user email address using verification token.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "token": "verification_token"
  }
  ```
- **Response (200):**
  ```json
  { "message": "Email verified successfully" }
  ```

#### `POST /auth/resend-verification`
- **Description:** Resends email verification link.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response (200):**
  ```json
  { "message": "Verification email sent" }
  ```

### 4.2. System Health

#### `GET /health`
- **Description:** Health check endpoint for monitoring system status.
- **Access:** Public
- **Response (200):**
  ```json
  {
    "status": "healthy",
    "timestamp": "timestamp",
    "version": "string",
    "services": {
      "database": "healthy",
      "ai_analysis": "healthy",
      "file_storage": "healthy"
    }
  }
  ```

### 4.3. Users & Profiles

#### `GET /users/me`
- **Description:** Retrieves the profile of the currently authenticated user.
- **Access:** Athlete, Scout
- **Response (200):** `Athlete Profile` or `Scout Profile` object.

#### `PUT /users/me`
- **Description:** Updates the profile of the currently authenticated user.
- **Access:** Athlete, Scout
- **Request Body:** Partial `Athlete Profile` or `Scout Profile` object.
- **Response (200):** Updated `Athlete Profile` or `Scout Profile` object.

#### `GET /athletes`
- **Description:** Searches for athletes based on filter criteria.
- **Access:** Scout
- **Query Parameters:**
  - `sport_category_id` (uuid)
  - `position` (string)
  - `min_age` (integer)
  - `max_age` (integer)
  - `gender` (string)
  - `location` (string)
  - `min_rating` (string: "exceptional" | "excellent" | "good" | "developing" | "needs_improvement")
  - `limit` (integer, default: 20)
  - `offset` (integer, default: 0)
- **Response (200):**
  ```json
  {
    "count": 150,
    "results": [ /* Array of Athlete Profile objects */ ]
  }
  ```

#### `GET /athletes/{athlete_id}`
- **Description:** Retrieves a specific athlete's public profile.
- **Access:** Scout
- **Response (200):** `Athlete Profile` object.

#### `GET /scouts`
- **Description:** Searches for scouts and organizations.
- **Access:** Athlete, Scout
- **Query Parameters:**
  - `organization` (string)
  - `location` (string)
  - `sport` (string)
  - `limit` (integer, default: 20)
  - `offset` (integer, default: 0)
- **Response (200):**
  ```json
  {
    "count": 50,
    "results": [ /* Array of Scout Profile objects */ ]
  }
  ```

#### `GET /scouts/{scout_id}`
- **Description:** Retrieves a specific scout's public profile.
- **Access:** Athlete, Scout
- **Response (200):** `Scout Profile` object.

#### `DELETE /users/me`
- **Description:** Deletes the authenticated user's account.
- **Access:** Athlete, Scout
- **Response (200):**
  ```json
  { "message": "Account deleted successfully" }
  ```



### 4.4. Media & Content

#### `POST /media/upload`
- **Description:** Uploads a media file directly to the server. AI analysis is automatically triggered upon successful upload.
- **Access:** Athlete
- **Request Body:** Multipart form data with file and metadata
  ```json
  {
    "file": "binary_file",
    "type": "video" | "image" | "reel",
    "description": "string" (optional)
  }
  ```
- **Response (202):** `Media` object with `ai_analysis.status` as `pending`.
- **File Limits:**
  - Maximum file size: 100MB for videos, 10MB for images
  - Supported formats: MP4, MOV, AVI (videos); JPG, PNG, GIF (images)
  - Maximum duration: 10 minutes for videos
- **Background Process:** AI analysis runs asynchronously with automatic retry mechanism:
  - Initial retry: 1 minute after failure
  - Exponential backoff: 2, 4, 8, 16, 32 minutes
  - Maximum 5 retries (configurable)
  - After max retries, status is permanently marked as "failed"

#### `GET /athletes/me/media`
- **Description:** Retrieves all media for the currently authenticated athlete.
- **Access:** Athlete
- **Response (200):** Array of `Media` objects.

#### `GET /athletes/{athlete_id}/media`
- **Description:** Retrieves all media for a specific athlete.
- **Access:** Scout
- **Response (200):** Array of `Media` objects.

#### `GET /reels/recommended`
- **Description:** Retrieves a feed of recommended reels for the scout. The algorithm uses the scout's profile and the AI ratings.
- **Access:** Scout
- **Response (200):** Array of `Media` objects where `type` is `reel`.

#### `GET /media/{media_id}/status`
- **Description:** Checks the status of AI analysis for a specific media file.
- **Access:** Athlete (owner only)
- **Response (200):** `Media` object with current AI analysis status.

#### `GET /media/{media_id}`
- **Description:** Retrieves details of a specific media file.
- **Access:** Athlete (owner only), Scout (for approved media)
- **Response (200):** `Media` object.

#### `POST /media/{media_id}/retry-analysis`
- **Description:** Manually retries AI analysis for failed media.
- **Access:** Athlete (owner only)
- **Response (200):**
  ```json
  { "message": "AI analysis retry initiated" }
  ```

### 4.5. Opportunity Board

#### `POST /opportunities`
- **Description:** Creates a new opportunity.
- **Access:** Scout
- **Request Body:** `Opportunity` object (without `id` or `scout_id`).
- **Response (201):** Full `Opportunity` object.

#### `GET /opportunities`
- **Description:** Lists all available opportunities with filters.
- **Access:** Athlete, Scout
- **Query Parameters:** `type`, `location`, `limit`, `offset`.
- **Response (200):** List of `Opportunity` objects.

#### `GET /opportunities/{opportunity_id}`
- **Description:** Retrieves the details of a specific opportunity.
- **Access:** Athlete, Scout
- **Response (200):** Full `Opportunity` object.

#### `POST /opportunities/{opportunity_id}/apply`
- **Description:** Allows an athlete to apply for an opportunity.
- **Access:** Athlete
- **Response (200):**
  ```json
  { "status": "application_submitted" }
  ```

#### `GET /scouts/me/opportunities`
- **Description:** Retrieves all opportunities created by the authenticated scout.
- **Access:** Scout
- **Query Parameters:** `status`, `limit`, `offset`
- **Response (200):** Array of `Opportunity` objects.

#### `PUT /opportunities/{opportunity_id}/toggle-status`
- **Description:** Toggles opportunity active/inactive status.
- **Access:** Scout (owner only)
- **Response (200):** Updated `Opportunity` object.

### 4.6. Admin

#### `POST /admin/scouts/{scout_id}/verify`
- **Description:** Verifies or rejects a scout's profile.
- **Access:** Admin
- **Request Body:**
  ```json
  { "status": "verified" | "rejected" }
  ```
- **Response (200):** Updated `Scout Profile`.

#### `GET /admin/users`
- **Description:** Retrieves all users with filtering options.
- **Access:** Admin
- **Query Parameters:** `role`, `status`, `limit`, `offset`
- **Response (200):** Array of user objects.

#### `PUT /admin/users/{user_id}/status`
- **Description:** Updates user status (suspend, activate, delete).
- **Access:** Admin
- **Request Body:**
  ```json
  {
    "status": "active" | "suspended" | "deleted",
    "reason": "string" (optional)
  }
  ```
- **Response (200):** Updated user object.

#### `GET /admin/verification/pending`
- **Description:** Retrieves pending verification documents.
- **Access:** Admin
- **Query Parameters:** `document_type`, `limit`, `offset`
- **Response (200):** Array of `Verification Document` objects.

#### `POST /admin/verification/{document_id}/review`
- **Description:** Reviews and approves/rejects verification documents.
- **Access:** Admin
- **Request Body:**
  ```json
  {
    "status": "approved" | "rejected",
    "notes": "string" (optional)
  }
  ```
- **Response (200):** Updated `Verification Document` object.

#### `GET /admin/reports`
- **Description:** Retrieves user reports for review.
- **Access:** Admin
- **Query Parameters:** `status`, `reason`, `limit`, `offset`
- **Response (200):** Array of `User Report` objects.

#### `POST /admin/reports/{report_id}/resolve`
- **Description:** Resolves a user report.
- **Access:** Admin
- **Request Body:**
  ```json
  {
    "action": "dismiss" | "warn_user" | "suspend_user" | "delete_user",
    "notes": "string" (optional)
  }
  ```
- **Response (200):** Updated `User Report` object.

#### `DELETE /admin/users/{user_id}`
- **Description:** Permanently deletes a user account.
- **Access:** Admin
- **Response (200):**
  ```json
  { "message": "User deleted successfully" }
  ```

#### `GET /admin/flags`
- **Description:** Retrieves all flags for admin review.
- **Access:** Admin
- **Query Parameters:** `status`, `content_type`, `reason`, `limit`, `offset`
- **Response (200):** Array of `Flag` objects.

#### `POST /admin/flags/{flag_id}/resolve`
- **Description:** Resolves a specific flag.
- **Access:** Admin
- **Request Body:**
  ```json
  {
    "action": "dismiss" | "take_action",
    "notes": "string" (optional)
  }
  ```
- **Response (200):** Updated `Flag` object.

### 4.7. Messaging System

#### `GET /conversations`
- **Description:** Retrieves all conversations for the authenticated user.
- **Access:** Athlete, Scout
- **Response (200):** Array of conversation objects.

#### `POST /conversations`
- **Description:** Creates a new conversation between an athlete and scout.
- **Access:** Athlete, Scout
- **Request Body:**
  ```json
  {
    "participant_id": "uuid",
    "initial_message": "string"
  }
  ```
- **Response (201):** Conversation object with messages.

#### `GET /conversations/{conversation_id}/messages`
- **Description:** Retrieves messages for a specific conversation.
- **Access:** Athlete, Scout (participants only)
- **Query Parameters:** `limit`, `offset`
- **Response (200):** Array of message objects.

#### `POST /conversations/{conversation_id}/messages`
- **Description:** Sends a message in a conversation.
- **Access:** Athlete, Scout (participants only)
- **Request Body:**
  ```json
  {
    "content": "string",
    "attachment_url": "url" (optional)
  }
  ```
- **Response (201):** Message object.

### 4.8. Password Management

#### `POST /auth/forgot-password`
- **Description:** Initiates password recovery process.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response (200):**
  ```json
  { "message": "Password reset email sent" }
  ```

#### `POST /auth/reset-password`
- **Description:** Resets password using reset token.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "token": "reset_token",
    "new_password": "newpassword"
  }
  ```
- **Response (200):**
  ```json
  { "message": "Password reset successfully" }
  ```



#### `POST /auth/change-password`
- **Description:** Changes password for authenticated user.
- **Access:** Authenticated users
- **Request Body:**
  ```json
  {
    "current_password": "currentpassword",
    "new_password": "newpassword"
  }
  ```
- **Response (200):**
  ```json
  { "message": "Password changed successfully" }
  ```

#### `POST /auth/refresh`
- **Description:** Refreshes the JWT token.
- **Access:** Authenticated users
- **Request Body:**
  ```json
  {
    "refresh_token": "refresh_token"
  }
  ```
- **Response (200):**
  ```json
  {
    "access_token": "new_jwt_token",
    "refresh_token": "new_refresh_token"
  }
  ```

#### `POST /auth/logout`
- **Description:** Logs out the user and invalidates tokens.
- **Access:** Authenticated users
- **Response (200):**
  ```json
  { "message": "Logged out successfully" }
  ```

### 4.9. Media Management

#### `DELETE /media/{media_id}`
- **Description:** Deletes a media file.
- **Access:** Athlete (owner only)
- **Response (204):** No content.

#### `PUT /media/{media_id}`
- **Description:** Updates media metadata.
- **Access:** Athlete (owner only)
- **Request Body:**
  ```json
  {
    "description": "string"
  }
  ```
- **Response (200):** Updated `Media` object.

### 4.10. Opportunity Management

#### `PUT /opportunities/{opportunity_id}`
- **Description:** Updates an opportunity.
- **Access:** Scout (owner only)
- **Request Body:** Partial `Opportunity` object.
- **Response (200):** Updated `Opportunity` object.

#### `DELETE /opportunities/{opportunity_id}`
- **Description:** Deletes an opportunity.
- **Access:** Scout (owner only)
- **Response (204):** No content.

#### `GET /opportunities/{opportunity_id}/applications`
- **Description:** Retrieves applications for an opportunity.
- **Access:** Scout (owner only)
- **Response (200):** Array of application objects.

### 4.11. Application Management

#### `GET /athletes/me/applications`
- **Description:** Retrieves all applications submitted by the athlete.
- **Access:** Athlete
- **Response (200):** Array of application objects.

#### `DELETE /opportunities/{opportunity_id}/applications/{application_id}`
- **Description:** Withdraws an application.
- **Access:** Athlete (applicant only)
- **Response (204):** No content.

#### `PUT /opportunities/{opportunity_id}/applications/{application_id}/status`
- **Description:** Updates application status (accept/reject).
- **Access:** Scout (opportunity owner only)
- **Request Body:**
  ```json
  {
    "status": "accepted" | "rejected",
    "feedback": "string" (optional)
  }
  ```
- **Response (200):** Updated `Application` object.

#### `GET /opportunities/{opportunity_id}/applications/{application_id}`
- **Description:** Retrieves details of a specific application.
- **Access:** Scout (opportunity owner only), Athlete (applicant only)
- **Response (200):** `Application` object.

### 4.12. Admin Analytics & Moderation

#### `GET /admin/analytics`
- **Description:** Retrieves platform usage statistics.
- **Access:** Admin
- **Query Parameters:** `start_date`, `end_date`
- **Response (200):**
  ```json
  {
    "total_athletes": "integer",
    "total_scouts": "integer",
    "total_opportunities": "integer",
    "total_applications": "integer",
    "active_conversations": "integer"
  }
  ```

#### `GET /athletes/me/analytics`
- **Description:** Retrieves analytics for the authenticated athlete.
- **Access:** Athlete
- **Query Parameters:** `start_date`, `end_date`
- **Response (200):**
  ```json
  {
    "profile_views": "integer",
    "media_views": "integer",
    "messages_received": "integer",
    "opportunities_applied": "integer",
    "applications_accepted": "integer"
  }
  ```

#### `GET /scouts/me/analytics`
- **Description:** Retrieves analytics for the authenticated scout.
- **Access:** Scout
- **Query Parameters:** `start_date`, `end_date`
- **Response (200):**
  ```json
  {
    "athletes_viewed": "integer",
    "searches_performed": "integer",
    "opportunities_created": "integer",
    "applications_received": "integer",
    "messages_sent": "integer"
  }
  ```

#### `GET /athletes/me/recommendations`
- **Description:** Retrieves personalized recommendations for the athlete.
- **Access:** Athlete
- **Query Parameters:** `limit`, `offset`
- **Response (200):** Array of recommended opportunities.

#### `GET /scouts/me/recommendations`
- **Description:** Retrieves personalized athlete recommendations for the scout.
- **Access:** Scout
- **Query Parameters:** `limit`, `offset`
- **Response (200):** Array of recommended athletes.

#### `GET /admin/content/pending`
- **Description:** Retrieves content pending moderation (both flagged content and content marked for review).
- **Access:** Admin
- **Query Parameters:** `type`, `moderation_status`, `priority`, `limit`, `offset`
- **Response (200):** Array of content objects requiring moderation.

#### `POST /admin/content/{content_id}/moderate`
- **Description:** Unified moderation endpoint for handling content approval, rejection, and flag resolution.
- **Access:** Admin
- **Request Body:**
  ```json
  {
    "action": "approve" | "reject" | "dismiss_flag" | "escalate" | "take_action",
    "reason": "string" (optional),
    "flag_id": "uuid" (optional, for flag-specific actions),
    "notes": "string" (optional)
  }
  ```
- **Response (200):** Updated content object with moderation status.

### 4.13. Content Flagging

#### `POST /content/{content_id}/flag`
- **Description:** Flags content for review by administrators.
- **Access:** Athlete, Scout
- **Request Body:**
  ```json
  {
    "reason": "inappropriate_content" | "fake_profile" | "spam" | "harassment" | "copyright" | "other",
    "description": "string" (optional),
    "evidence_url": "url" (optional)
  }
  ```
- **Response (200):**
  ```json
  { "message": "Content flagged for review" }
  ```

#### `GET /content/{content_id}/flags`
- **Description:** Retrieves all flags for a specific content item (admin only).
- **Access:** Admin
- **Response (200):** Array of flag objects.

### 4.14. Notifications

#### `GET /notifications`
- **Description:** Retrieves notifications for the authenticated user.
- **Access:** Athlete, Scout
- **Query Parameters:** `type`, `unread_only`, `limit`, `offset`
- **Response (200):** Array of notification objects.

#### `PUT /notifications/{notification_id}/read`
- **Description:** Marks a notification as read.
- **Access:** Athlete, Scout
- **Response (200):** Updated notification object.

#### `PUT /notifications/read-all`
- **Description:** Marks all notifications as read.
- **Access:** Athlete, Scout
- **Response (200):**
  ```json
  { "message": "All notifications marked as read" }
  ```

### 4.15. User Management

#### `POST /users/{user_id}/block`
- **Description:** Blocks a user from contacting you.
- **Access:** Athlete, Scout
- **Response (200):**
  ```json
  { "message": "User blocked successfully" }
  ```

#### `POST /users/{user_id}/report`
- **Description:** Reports a user for inappropriate behavior.
- **Access:** Athlete, Scout
- **Request Body:**
  ```json
  {
    "reason": "harassment" | "spam" | "fake_profile" | "inappropriate_content" | "other",
    "description": "string",
    "evidence_url": "url" (optional)
  }
  ```
- **Response (200):**
  ```json
  { "message": "User reported successfully" }
  ```

#### `POST /athletes/me/verify`
- **Description:** Submits verification documents for athlete profile.
- **Access:** Athlete
- **Request Body:**
  ```json
  {
    "document_type": "id_card" | "passport" | "school_id" | "other",
    "document_url": "url",
    "additional_info": "string" (optional)
  }
  ```
- **Response (200):**
  ```json
  { "message": "Verification submitted for review" }
  ```

### 4.16. Search & History

#### `GET /search/history`
- **Description:** Retrieves search history for the authenticated user.
- **Access:** Athlete, Scout
- **Query Parameters:** `type`, `limit`, `offset`
- **Response (200):** Array of search history objects.

#### `DELETE /search/history/{search_id}`
- **Description:** Deletes a specific search from history.
- **Access:** Athlete, Scout
- **Response (204):** No content.

#### `DELETE /search/history`
- **Description:** Clears all search history.
- **Access:** Athlete, Scout
- **Response (200):**
  ```json
  { "message": "Search history cleared" }
  ```

#### `POST /search/athletes`
- **Description:** Advanced athlete search with complex filters.
- **Access:** Scout
- **Request Body:**
  ```json
  {
    "sport_category_id": "uuid",
    "position": "string",
    "age_range": {
      "min": "integer",
      "max": "integer"
    },
    "gender": "string",
    "location": "string",
    "rating": "string",
    "stats_filters": "object" (dynamic based on sport category stats_fields),
    "limit": "integer",
    "offset": "integer"
  }
  ```
- **Response (200):**
  ```json
  {
    "count": "integer",
    "results": [ /* Array of Athlete Profile objects */ ]
  }
  ```

#### `POST /search/opportunities`
- **Description:** Advanced opportunity search with complex filters.
- **Access:** Athlete, Scout
- **Request Body:**
  ```json
  {
    "type": "string",
    "location": "string",
    "date_range": {
      "start": "date",
      "end": "date"
    },
    "sport_category_id": "uuid",
    "limit": "integer",
    "offset": "integer"
  }
  ```
- **Response (200):**
  ```json
  {
    "count": "integer",
    "results": [ /* Array of Opportunity objects */ ]
  }
  ```

### 4.17. Stats & Achievements Management

#### `POST /athletes/me/stats`
- **Description:** Creates or updates athlete statistics.
- **Access:** Athlete
- **Request Body:** `Stats/Achievements` object (without `id` or `athlete_id`).
- **Response (201):** Full `Stats/Achievements` object.

#### `GET /athletes/me/stats`
- **Description:** Retrieves all stats for the authenticated athlete.
- **Access:** Athlete
- **Response (200):** Array of `Stats/Achievements` objects.

#### `GET /athletes/{athlete_id}/stats`
- **Description:** Retrieves stats for a specific athlete.
- **Access:** Scout
- **Response (200):** Array of `Stats/Achievements` objects.

#### `PUT /athletes/me/stats/{stats_id}`
- **Description:** Updates athlete statistics.
- **Access:** Athlete (owner only)
- **Request Body:** Partial `Stats/Achievements` object.
- **Response (200):** Updated `Stats/Achievements` object.

#### `DELETE /athletes/me/stats/{stats_id}`
- **Description:** Deletes athlete statistics.
- **Access:** Athlete (owner only)
- **Response (204):** No content.

### 4.18. Organization Management

#### `POST /organizations`
- **Description:** Creates a new organization.
- **Access:** Admin
- **Request Body:** `Organization` object (without `id`).
- **Response (201):** Full `Organization` object.

#### `GET /organizations`
- **Description:** Lists all organizations.
- **Access:** Athlete, Scout
- **Query Parameters:** `type`, `location`, `limit`, `offset`.
- **Response (200):** Array of `Organization` objects.

#### `GET /organizations/{organization_id}`
- **Description:** Retrieves a specific organization.
- **Access:** Athlete, Scout
- **Response (200):** `Organization` object.

#### `PUT /organizations/{organization_id}`
- **Description:** Updates an organization.
- **Access:** Admin
- **Request Body:** Partial `Organization` object.
- **Response (200):** Updated `Organization` object.

### 4.19. Message Management

#### `PUT /conversations/{conversation_id}/messages/{message_id}/read`
- **Description:** Marks a message as read.
- **Access:** Athlete, Scout (participants only)
- **Response (200):** Updated `Message` object.

#### `PUT /conversations/{conversation_id}/messages/read-all`
- **Description:** Marks all messages in a conversation as read.
- **Access:** Athlete, Scout (participants only)
- **Response (200):**
  ```json
  { "message": "All messages marked as read" }
  ```

### 4.20. User Settings Management

#### `GET /users/me/settings`
- **Description:** Retrieves user settings.
- **Access:** Athlete, Scout
- **Response (200):** User settings object.

#### `PUT /users/me/settings`
- **Description:** Updates user settings.
- **Access:** Athlete, Scout
- **Request Body:**
  ```json
  {
    "notifications_enabled": "boolean",
    "privacy_level": "public" | "private" | "friends_only"
  }
  ```
- **Response (200):** Updated user settings object.

### 4.21. Blocked Users Management

#### `GET /users/me/blocked`
- **Description:** Retrieves list of users blocked by the authenticated user.
- **Access:** Athlete, Scout
- **Response (200):** Array of `Blocked User` objects.

#### `DELETE /users/me/blocked/{blocked_user_id}`
- **Description:** Unblocks a user.
- **Access:** Athlete, Scout
- **Response (200):**
  ```json
  { "message": "User unblocked successfully" }
  ```

### 4.22. Verification Management

#### `GET /athletes/me/verification/status`
- **Description:** Checks the verification status of the authenticated athlete.
- **Access:** Athlete
- **Response (200):** Verification status object.

#### `GET /athletes/me/verification/documents`
- **Description:** Retrieves all verification documents submitted by the athlete.
- **Access:** Athlete
- **Response (200):** Array of `Verification Document` objects.

### 4.23. Conversation Management

#### `DELETE /conversations/{conversation_id}`
- **Description:** Deletes a conversation and all its messages.
- **Access:** Athlete, Scout (participants only)
- **Response (204):** No content.

#### `PUT /conversations/{conversation_id}/archive`
- **Description:** Archives a conversation (hides from main list but keeps messages).
- **Access:** Athlete, Scout (participants only)
- **Response (200):** Updated conversation object.

### 4.24. Bulk Operations

#### `POST /media/bulk-upload`
- **Description:** Uploads multiple media files in a single request.
- **Access:** Athlete
- **Request Body:** Multipart form data with multiple files
  ```json
  {
    "files": ["binary_file1", "binary_file2", ...],
    "metadata": [
      {
        "type": "video" | "image" | "reel",
        "description": "string" (optional),
        "sport": "string" (optional),
        "tags": ["string"] (optional)
      }
    ]
  }
  ```
- **Response (202):** Array of `Media` objects with upload progress.

#### `PUT /notifications/bulk-read`
- **Description:** Marks multiple notifications as read.
- **Access:** Athlete, Scout
- **Request Body:**
  ```json
  {
    "notification_ids": ["uuid1", "uuid2", ...]
  }
  ```
- **Response (200):**
  ```json
  { "message": "Notifications marked as read" }
  ```

#### `DELETE /media/bulk-delete`
- **Description:** Deletes multiple media files.
- **Access:** Athlete (owner only)
- **Request Body:**
  ```json
  {
    "media_ids": ["uuid1", "uuid2", ...]
  }
  ```
- **Response (200):**
  ```json
  { "message": "Media files deleted successfully" }
  ```

### 4.25. Sport Category Management

#### `POST /admin/sport-categories`
- **Description:** Creates a new sport category with predefined stats fields and achievement types.
- **Access:** Admin
- **Request Body:**
  ```json
  {
    "name": "string",
    "description": "string",
    "icon_url": "url" (optional),
    "stats_fields": [
      {
        "key": "string",
        "label": "string",
        "type": "integer" | "float" | "string" | "boolean",
        "unit": "string" (optional),
        "required": "boolean",
        "default_value": "any" (optional),
        "validation": {
          "min": "number" (optional),
          "max": "number" (optional),
          "pattern": "string" (optional)
        },
        "display_order": "integer"
      }
    ],
    "achievement_types": [
      {
        "key": "string",
        "label": "string",
        "description": "string",
        "icon_url": "url" (optional)
      }
    ]
  }
  ```
- **Response (201):** Full `Sport Category` object.

#### `GET /sport-categories`
- **Description:** Lists all active sport categories.
- **Access:** Athlete, Scout
- **Query Parameters:** `limit`, `offset`
- **Response (200):** Array of `Sport Category` objects.

#### `GET /admin/sport-categories`
- **Description:** Lists all sport categories (including inactive ones).
- **Access:** Admin
- **Query Parameters:** `is_active`, `limit`, `offset`
- **Response (200):** Array of `Sport Category` objects.

#### `GET /sport-categories/{category_id}`
- **Description:** Retrieves a specific sport category.
- **Access:** Athlete, Scout
- **Response (200):** `Sport Category` object.

#### `PUT /admin/sport-categories/{category_id}`
- **Description:** Updates a sport category.
- **Access:** Admin
- **Request Body:** Partial `Sport Category` object.
- **Response (200):** Updated `Sport Category` object.

#### `DELETE /admin/sport-categories/{category_id}`
- **Description:** Deactivates a sport category (soft delete).
- **Access:** Admin
- **Response (200):**
  ```json
  { "message": "Sport category deactivated successfully" }
  ```

#### `POST /admin/sport-categories/{category_id}/activate`
- **Description:** Reactivates a deactivated sport category.
- **Access:** Admin
- **Response (200):**
  ```json
  { "message": "Sport category activated successfully" }
  ```

#### `GET /sport-categories/{category_id}/stats-template`
- **Description:** Retrieves the stats template for a sport category.
- **Access:** Athlete, Scout
- **Response (200):**
  ```json
  {
    "category": "Sport Category" object,
    "stats_template": "object" (empty stats object with proper structure),
    "achievement_types": ["array of achievement types"]
  }
  ```

### Example Sport Categories

#### Soccer/Football Category
```json
{
  "name": "Soccer/Football",
  "description": "Association football",
  "stats_fields": [
    {
      "key": "games_played",
      "label": "Games Played",
      "type": "integer",
      "required": true,
      "display_order": 1
    },
    {
      "key": "goals_scored",
      "label": "Goals Scored",
      "type": "integer",
      "unit": "goals",
      "required": false,
      "display_order": 2
    },
    {
      "key": "assists",
      "label": "Assists",
      "type": "integer",
      "unit": "assists",
      "required": false,
      "display_order": 3
    },
    {
      "key": "clean_sheets",
      "label": "Clean Sheets",
      "type": "integer",
      "unit": "clean sheets",
      "required": false,
      "display_order": 4
    },
    {
      "key": "yellow_cards",
      "label": "Yellow Cards",
      "type": "integer",
      "unit": "cards",
      "required": false,
      "display_order": 5
    },
    {
      "key": "red_cards",
      "label": "Red Cards",
      "type": "integer",
      "unit": "cards",
      "required": false,
      "display_order": 6
    }
  ],
  "achievement_types": [
    {
      "key": "top_scorer",
      "label": "Top Scorer",
      "description": "Highest goal scorer in league/competition"
    },
    {
      "key": "best_player",
      "label": "Best Player",
      "description": "Player of the season/tournament"
    },
    {
      "key": "championship_winner",
      "label": "Championship Winner",
      "description": "Won league championship"
    }
  ]
}
```

#### Basketball Category
```json
{
  "name": "Basketball",
  "description": "Basketball",
  "stats_fields": [
    {
      "key": "games_played",
      "label": "Games Played",
      "type": "integer",
      "required": true,
      "display_order": 1
    },
    {
      "key": "points_per_game",
      "label": "Points Per Game",
      "type": "float",
      "unit": "ppg",
      "required": false,
      "validation": {
        "min": 0,
        "max": 100
      },
      "display_order": 2
    },
    {
      "key": "rebounds_per_game",
      "label": "Rebounds Per Game",
      "type": "float",
      "unit": "rpg",
      "required": false,
      "display_order": 3
    },
    {
      "key": "assists_per_game",
      "label": "Assists Per Game",
      "type": "float",
      "unit": "apg",
      "required": false,
      "display_order": 4
    },
    {
      "key": "steals_per_game",
      "label": "Steals Per Game",
      "type": "float",
      "unit": "spg",
      "required": false,
      "display_order": 5
    },
    {
      "key": "blocks_per_game",
      "label": "Blocks Per Game",
      "type": "float",
      "unit": "bpg",
      "required": false,
      "display_order": 6
    }
  ],
  "achievement_types": [
    {
      "key": "mvp",
      "label": "MVP",
      "description": "Most Valuable Player"
    },
    {
      "key": "all_star",
      "label": "All-Star",
      "description": "Selected for All-Star game"
    },
    {
      "key": "championship_winner",
      "label": "Championship Winner",
      "description": "Won league championship"
    }
  ]
}
```

---

## 5. Error Response Format

All error responses follow this standardized format:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object" (optional)
  }
}
```

### Common Error Codes:
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `409` - Conflict (resource already exists)
- `422` - Unprocessable Entity (business logic errors)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

### Error Response Examples:

#### Validation Error (400)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "email": ["Invalid email format"],
      "password": ["Password must be at least 8 characters"]
    }
  }
}
```

#### Authentication Error (401)
```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Invalid or expired authentication token"
  }
}
```

#### Rate Limit Error (429)
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later.",
    "details": {
      "retry_after": 60
    }
  }
}
```

---

## 6. WebSocket Endpoints

### Real-time Messaging
- **Connection:** `ws://api/v1/ws/messages?token=<jwt-token>`
- **Authentication:** JWT token in query parameter
- **Events:**
  - `message_received` - New message in conversation
  - `message_read` - Message marked as read
  - `typing` - User typing indicator
  - `user_online` - User comes online
  - `user_offline` - User goes offline
  - `notification` - Real-time notification

### WebSocket Message Format
```json
{
  "type": "event_type",
  "data": "object",
  "timestamp": "timestamp"
}
```

### Connection Management
- **Heartbeat:** Send ping every 30 seconds to maintain connection
- **Reconnection:** Automatic reconnection with exponential backoff
- **Error Handling:** Connection errors return appropriate HTTP status codes
