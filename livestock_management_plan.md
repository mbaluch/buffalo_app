# Livestock Management Platform - Comprehensive Specification

## Context

This specification defines a regional livestock management web application for multiple agricultural cooperatives (JZD - Jednotné zemědělské družstvo) in the Czech Republic. The platform will serve 100,000 users across multiple cooperatives, enabling them to register livestock (initially cows and bulls/oxen), search for breeding matches, schedule inseminations, and track pregnancy status.

**Problem Statement:** Agricultural cooperatives need a centralized system to:
- Register and manage livestock with detailed attributes
- Enable sperm collectors and insemination companies to find suitable breeding matches
- Schedule appointments for viewing livestock and performing inseminations
- Track pregnancy status and availability for breeding
- Provide REST API access for integration with external systems

**Intended Outcome:** A scalable, multi-tenant Java web application with:
- Simple, readable user interface
- Comprehensive search capabilities based on livestock attributes
- Appointment scheduling system
- Pregnancy tracking and availability management
- REST API for import/export and integration

---

## 1. Technology Stack

### Backend
- **Framework:** Spring Boot 3.2+ (Java 17+)
- **Database:** PostgreSQL 15+ with JSONB support for flexible attributes
- **Caching:** Redis for search results and session management
- **Search Engine:** Elasticsearch for complex attribute queries and full-text search
- **File Storage:** AWS S3 or MinIO (S3-compatible) for livestock photos
- **Security:** Spring Security with JWT authentication
- **Build Tool:** Maven or Gradle
- **Database Migration:** Flyway

### Frontend
- **Primary Option:** Thymeleaf + Bootstrap 5 (simple, readable UI as required)
- **JavaScript:** Alpine.js for lightweight interactivity
- **Components:**
  - Dropzone.js for photo uploads
  - Flatpickr for date/time pickers
  - Leaflet.js for maps and location visualization
  
### Infrastructure
- **Containerization:** Docker
- **Orchestration:** Kubernetes for 100k user scale
- **Load Balancer:** NGINX
- **Monitoring:** Prometheus + Grafana
- **Logging:** ELK Stack (Elasticsearch, Logstash, Kibana)
- **Message Queue:** RabbitMQ for async processing

---

## 2. System Architecture

### Multi-Tenancy Strategy

**Shared Database with JZD Isolation:**
- All tables include `jzd_id` foreign key for cooperative isolation
- Row-Level Security enforced at application layer
- `JzdContextHolder` ThreadLocal stores current user's JZD context
- All queries automatically filtered by authenticated user's JZD
- Cross-JZD search allowed for breeding coordination (regional platform model)

### Key Architectural Components

1. **Web Layer:** Spring MVC controllers for UI + REST controllers for API
2. **Service Layer:** Business logic, validation, pregnancy tracking
3. **Repository Layer:** Spring Data JPA with custom queries
4. **Security Layer:** JWT authentication, role-based authorization, JZD context filtering
5. **Search Layer:** Elasticsearch integration for advanced queries
6. **Storage Layer:** S3/MinIO client for photo management
7. **Async Layer:** RabbitMQ consumers for photo processing, search indexing

---

## 3. Data Model

### Core Entities

#### 1. JZD (Agricultural Cooperative)
```sql
CREATE TABLE jzd (
    id BIGSERIAL PRIMARY KEY,
    registration_number VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'CZ',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    contact_phone VARCHAR(50),
    contact_email VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. User
```sql
CREATE TABLE app_user (
    id BIGSERIAL PRIMARY KEY,
    jzd_id BIGINT REFERENCES jzd(id) NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(50),
    role VARCHAR(50) NOT NULL, -- JZD_ADMIN, SPERM_COLLECTOR, INSEMINATOR, FARM_OWNER, VETERINARIAN
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_user_jzd ON app_user(jzd_id);
CREATE INDEX idx_user_role ON app_user(role);
```

#### 3. Farm
```sql
CREATE TABLE farm (
    id BIGSERIAL PRIMARY KEY,
    jzd_id BIGINT REFERENCES jzd(id) NOT NULL,
    owner_id BIGINT REFERENCES app_user(id),
    name VARCHAR(255) NOT NULL,
    registration_number VARCHAR(50),
    address TEXT,
    city VARCHAR(100),
    postal_code VARCHAR(20),
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    contact_phone VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_farm_jzd ON farm(jzd_id);
CREATE INDEX idx_farm_owner ON farm(owner_id);
CREATE INDEX idx_farm_location ON farm(latitude, longitude);
```

#### 4. Livestock Type
```sql
CREATE TABLE livestock_type (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, -- COW, BULL, OX
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL, -- CATTLE (allows future: SHEEP, PIG, etc.)
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Initial data: COW, BULL, OX (all category=CATTLE)
```

#### 5. Attribute Definition (Flexible Schema)
```sql
CREATE TABLE attribute_definition (
    id BIGSERIAL PRIMARY KEY,
    livestock_type_id BIGINT REFERENCES livestock_type(id),
    attribute_key VARCHAR(100) NOT NULL, -- e.g., "breed", "weight", "leg_length"
    attribute_name VARCHAR(255) NOT NULL, -- Display name
    data_type VARCHAR(50) NOT NULL, -- STRING, NUMBER, DECIMAL, BOOLEAN, DATE, ENUM
    unit VARCHAR(50), -- kg, cm, etc.
    is_searchable BOOLEAN DEFAULT true,
    is_required BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    enum_values JSONB, -- For ENUM type: ["Holstein", "Angus", "Jersey"]
    validation_rules JSONB, -- {"min": 0, "max": 2000, "pattern": "regex"}
    display_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(livestock_type_id, attribute_key)
);
CREATE INDEX idx_attr_def_type ON attribute_definition(livestock_type_id);
CREATE INDEX idx_attr_def_searchable ON attribute_definition(is_searchable);
```

**Initial Common Cattle Attributes (modular, replaceable):**
- breed (ENUM)
- birth_date (DATE)
- weight (DECIMAL, kg)
- height (DECIMAL, cm)
- leg_length (DECIMAL, cm)
- coat_color (STRING)
- ear_tag_number (STRING)
- genetic_markers (STRING)
- milk_production (DECIMAL, liters/day - for cows)
- horn_status (ENUM: HORNED, POLLED, DEHORNED)

#### 6. Livestock
```sql
CREATE TABLE livestock (
    id BIGSERIAL PRIMARY KEY,
    jzd_id BIGINT REFERENCES jzd(id) NOT NULL,
    farm_id BIGINT REFERENCES farm(id) NOT NULL,
    livestock_type_id BIGINT REFERENCES livestock_type(id) NOT NULL,
    registration_number VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255),
    sex VARCHAR(10) NOT NULL, -- MALE, FEMALE
    status VARCHAR(50) DEFAULT 'ACTIVE', -- ACTIVE, INACTIVE, DECEASED, SOLD
    
    -- Flexible attributes stored as JSONB
    attributes JSONB NOT NULL DEFAULT '{}',
    
    -- Breeding availability
    is_available_for_breeding BOOLEAN DEFAULT true,
    
    -- Pregnancy tracking (for cows)
    pregnancy_status VARCHAR(50), -- NULL, PREGNANT, CALVED
    pregnancy_start_date DATE,
    expected_calving_date DATE,
    actual_calving_date DATE,
    
    -- Audit fields
    created_by BIGINT REFERENCES app_user(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_sex CHECK (sex IN ('MALE', 'FEMALE')),
    CONSTRAINT check_pregnancy_logic CHECK (
        (sex = 'FEMALE') OR (pregnancy_status IS NULL)
    )
);

CREATE INDEX idx_livestock_jzd ON livestock(jzd_id);
CREATE INDEX idx_livestock_farm ON livestock(farm_id);
CREATE INDEX idx_livestock_type ON livestock(livestock_type_id);
CREATE INDEX idx_livestock_status ON livestock(status);
CREATE INDEX idx_livestock_available ON livestock(is_available_for_breeding);
CREATE INDEX idx_livestock_pregnancy ON livestock(pregnancy_status);
-- GIN index for JSONB attribute queries
CREATE INDEX idx_livestock_attributes ON livestock USING GIN(attributes);
```

**Example JSONB attributes data:**
```json
{
  "breed": "Holstein",
  "birth_date": "2024-03-15",
  "weight": 650.5,
  "height": 152.0,
  "leg_length": 45.2,
  "coat_color": "Black and White",
  "ear_tag_number": "CZ-12345",
  "genetic_markers": "A2A2 Beta-casein",
  "milk_production": 28.5,
  "horn_status": "POLLED"
}
```

#### 7. Livestock Photo
```sql
CREATE TABLE livestock_photo (
    id BIGSERIAL PRIMARY KEY,
    livestock_id BIGINT REFERENCES livestock(id) ON DELETE CASCADE,
    file_key VARCHAR(500) NOT NULL, -- S3 object key
    file_url TEXT NOT NULL, -- Full S3 URL
    thumbnail_url TEXT, -- Thumbnail URL (300x300px)
    file_size_bytes BIGINT,
    mime_type VARCHAR(50),
    is_primary BOOLEAN DEFAULT false,
    display_order INT DEFAULT 0,
    uploaded_by BIGINT REFERENCES app_user(id),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_photo_livestock ON livestock_photo(livestock_id);
CREATE INDEX idx_photo_primary ON livestock_photo(livestock_id, is_primary);
```

#### 8. Appointment
```sql
CREATE TABLE appointment (
    id BIGSERIAL PRIMARY KEY,
    jzd_id BIGINT REFERENCES jzd(id) NOT NULL,
    livestock_id BIGINT REFERENCES livestock(id) NOT NULL,
    appointment_type VARCHAR(50) NOT NULL, -- VIEWING, INSEMINATION, CHECKUP
    status VARCHAR(50) DEFAULT 'SCHEDULED', -- SCHEDULED, CONFIRMED, COMPLETED, CANCELLED
    
    scheduled_date DATE NOT NULL,
    scheduled_time TIME NOT NULL,
    duration_minutes INT DEFAULT 60,
    
    requester_id BIGINT REFERENCES app_user(id) NOT NULL, -- Who requested
    assignee_id BIGINT REFERENCES app_user(id), -- Vet or inseminator assigned
    
    notes TEXT,
    cancellation_reason TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_appointment_type CHECK (appointment_type IN ('VIEWING', 'INSEMINATION', 'CHECKUP'))
);
CREATE INDEX idx_appointment_jzd ON appointment(jzd_id);
CREATE INDEX idx_appointment_livestock ON appointment(livestock_id);
CREATE INDEX idx_appointment_date ON appointment(scheduled_date);
CREATE INDEX idx_appointment_requester ON appointment(requester_id);
CREATE INDEX idx_appointment_assignee ON appointment(assignee_id);
```

#### 9. Insemination Record
```sql
CREATE TABLE insemination_record (
    id BIGSERIAL PRIMARY KEY,
    jzd_id BIGINT REFERENCES jzd(id) NOT NULL,
    cow_id BIGINT REFERENCES livestock(id) NOT NULL,
    bull_id BIGINT REFERENCES livestock(id), -- NULL if external bull
    external_bull_info JSONB, -- For bulls not in system
    
    insemination_date DATE NOT NULL,
    insemination_time TIME,
    method VARCHAR(50) DEFAULT 'ARTIFICIAL', -- ARTIFICIAL, NATURAL
    
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, CONFIRMED, FAILED
    pregnancy_confirmed BOOLEAN DEFAULT false,
    pregnancy_confirmed_date DATE,
    pregnancy_confirmed_by BIGINT REFERENCES app_user(id),
    
    performed_by BIGINT REFERENCES app_user(id), -- Inseminator
    veterinarian_id BIGINT REFERENCES app_user(id),
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_insemination_method CHECK (method IN ('ARTIFICIAL', 'NATURAL'))
);
CREATE INDEX idx_insemination_jzd ON insemination_record(jzd_id);
CREATE INDEX idx_insemination_cow ON insemination_record(cow_id);
CREATE INDEX idx_insemination_bull ON insemination_record(bull_id);
CREATE INDEX idx_insemination_date ON insemination_record(insemination_date);
CREATE INDEX idx_insemination_status ON insemination_record(status);
```

#### 10. Health Record
```sql
CREATE TABLE health_record (
    id BIGSERIAL PRIMARY KEY,
    jzd_id BIGINT REFERENCES jzd(id) NOT NULL,
    livestock_id BIGINT REFERENCES livestock(id) NOT NULL,
    record_type VARCHAR(50) NOT NULL, -- CHECKUP, TREATMENT, VACCINATION, DIAGNOSIS, CALVING
    record_date DATE NOT NULL,
    
    veterinarian_id BIGINT REFERENCES app_user(id),
    
    diagnosis TEXT,
    treatment TEXT,
    medications JSONB, -- [{"name": "Penicillin", "dosage": "10ml", "duration": "5 days"}]
    
    notes TEXT,
    follow_up_required BOOLEAN DEFAULT false,
    follow_up_date DATE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_health_jzd ON health_record(jzd_id);
CREATE INDEX idx_health_livestock ON health_record(livestock_id);
CREATE INDEX idx_health_date ON health_record(record_date);
CREATE INDEX idx_health_vet ON health_record(veterinarian_id);
```

#### 11. Breeding Match History (Optional - for tracking match recommendations)
```sql
CREATE TABLE breeding_match_recommendation (
    id BIGSERIAL PRIMARY KEY,
    requested_by BIGINT REFERENCES app_user(id) NOT NULL,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Search criteria
    desired_attributes JSONB NOT NULL,
    location_lat DECIMAL(10, 8),
    location_lon DECIMAL(11, 8),
    search_radius_km INT,
    
    -- Recommended pairing
    cow_id BIGINT REFERENCES livestock(id),
    bull_id BIGINT REFERENCES livestock(id),
    
    match_score DECIMAL(5, 2),
    predicted_offspring JSONB,
    match_reasoning JSONB,
    
    -- User action
    was_accepted BOOLEAN,
    insemination_record_id BIGINT REFERENCES insemination_record(id),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_breeding_match_user ON breeding_match_recommendation(requested_by);
CREATE INDEX idx_breeding_match_cow ON breeding_match_recommendation(cow_id);
CREATE INDEX idx_breeding_match_bull ON breeding_match_recommendation(bull_id);
CREATE INDEX idx_breeding_match_accepted ON breeding_match_recommendation(was_accepted);
```

**Purpose:** Track which breeding matches were recommended and which were accepted. This enables:
- Historical analysis of prediction accuracy
- Machine learning model training (actual vs. predicted offspring)
- User preference learning
- Success rate reporting

---

## 4. Flexible Attribute System

### Design Rationale

The attribute system must be **"easily replaceable with attributes from external file"** as specified. This enables:
- Custom attributes per cooperative
- Future import of official breed registry standards
- Easy updates without code changes

### Implementation Strategy

**1. Database-Driven Attribute Definitions**
- Attributes stored in `attribute_definition` table
- Support for multiple data types: STRING, NUMBER, DECIMAL, BOOLEAN, DATE, ENUM
- Validation rules stored as JSONB (min, max, pattern, etc.)
- ENUM values stored as JSONB array

**2. Dynamic Livestock Attributes in JSONB**
- All livestock attributes stored in single JSONB column
- PostgreSQL GIN index for efficient querying
- Schema-less storage allows flexibility
- Validated against attribute definitions at application layer

**3. Import/Export Capabilities**

**CSV Format for Attribute Definitions:**
```csv
livestock_type,attribute_key,attribute_name,data_type,unit,is_required,is_searchable,enum_values,validation_rules
CATTLE,breed,Breed,ENUM,,true,true,"Holstein|Angus|Jersey|Hereford",
CATTLE,weight,Weight (kg),DECIMAL,kg,true,true,,"min:0|max:2000"
CATTLE,height,Height (cm),DECIMAL,cm,false,true,,"min:0|max:200"
CATTLE,leg_length,Leg Length (cm),DECIMAL,cm,false,true,,"min:0|max:100"
CATTLE,birth_date,Birth Date,DATE,,true,true,,
CATTLE,coat_color,Coat Color,STRING,,false,false,,
```

**JSON Format for Attribute Definitions:**
```json
[
  {
    "livestockType": "CATTLE",
    "attributeKey": "breed",
    "attributeName": "Breed",
    "dataType": "ENUM",
    "unit": null,
    "isRequired": true,
    "isSearchable": true,
    "enumValues": ["Holstein", "Angus", "Jersey", "Hereford"],
    "validationRules": {}
  },
  {
    "livestockType": "CATTLE",
    "attributeKey": "weight",
    "attributeName": "Weight",
    "dataType": "DECIMAL",
    "unit": "kg",
    "isRequired": true,
    "isSearchable": true,
    "enumValues": null,
    "validationRules": {"min": 0, "max": 2000}
  }
]
```

**4. Dynamic Form Generation**
- Frontend reads attribute definitions from API
- Generates form fields based on data type
- Client-side validation from validation rules
- Automatically adapts when definitions change

**5. Attribute Versioning (Future Enhancement)**
- Track changes to attribute definitions
- Migrate existing livestock data when definitions change
- Maintain historical attribute definitions for reporting

---

## 5. REST API Design

### Base URL: `/api/v1`

### Authentication
All API endpoints require JWT token in `Authorization: Bearer <token>` header (except login/register).

### Common Response Formats

**Success Response:**
```json
{
  "success": true,
  "data": { ... },
  "timestamp": "2026-06-27T10:30:00Z"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {"field": "weight", "message": "Weight must be between 0 and 2000"}
    ]
  },
  "timestamp": "2026-06-27T10:30:00Z"
}
```

**Paginated Response:**
```json
{
  "success": true,
  "data": [ ... ],
  "pagination": {
    "page": 0,
    "size": 20,
    "totalElements": 157,
    "totalPages": 8
  }
}
```

### Endpoints

#### Authentication
```
POST   /api/v1/auth/login
POST   /api/v1/auth/register
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
```

#### Livestock Management
```
GET    /api/v1/livestock
       Query params: page, size, sort, livestockTypeId, farmId, status, availableForBreeding
       
GET    /api/v1/livestock/{id}
       Returns: Full livestock details with attributes, photos, location

POST   /api/v1/livestock
       Body: {
         "farmId": 42,
         "livestockTypeId": 1,
         "registrationNumber": "CZ-001-2026-00123",
         "name": "Bessie",
         "sex": "FEMALE",
         "attributes": {
           "breed": "Holstein",
           "birth_date": "2024-03-15",
           "weight": 650.5,
           "height": 152.0
         }
       }

PUT    /api/v1/livestock/{id}
       Body: Same as POST (partial updates allowed)

DELETE /api/v1/livestock/{id}
       Soft delete (sets status=INACTIVE)

POST   /api/v1/livestock/{id}/photos
       Content-Type: multipart/form-data
       Field: photo (file), isPrimary (boolean)

DELETE /api/v1/livestock/{id}/photos/{photoId}
```

#### Advanced Search
```
POST   /api/v1/search/livestock
       Body: {
         "livestockTypeId": 1,
         "sex": "MALE", // Can search for MALE (bulls) or FEMALE (cows)
         "availableForBreeding": true,
         "attributeFilters": {
           "breed": "Holstein",
           "weight": {"min": 500, "max": 700},
           "height": {"min": 140, "max": 160},
           "leg_length": {"min": 40, "max": 50}
         },
         "location": {
           "latitude": 50.0755,
           "longitude": 14.4378,
           "radiusKm": 50
         },
         "page": 0,
         "size": 20,
         "sort": "attributes.weight:desc"
       }
       
       Returns: Paginated livestock with distance from search location
       
       Note: This endpoint works bidirectionally - search for bulls OR cows
       based on any criteria. Use sex filter to specify which to search for.
```

#### Outcome-Based Breeding Match (Genetic Planning)
```
POST   /api/v1/search/breeding-match
       Body: {
         "desiredOffspringAttributes": {
           "breed": "Holstein",
           "target_weight": {"min": 700, "max": 800},
           "target_height": {"min": 155, "max": 165},
           "genetic_markers": "A2A2 Beta-casein",
           "milk_production": {"min": 30}
         },
         "location": {
           "latitude": 50.0755,
           "longitude": 14.4378,
           "radiusKm": 100
         },
         "constraints": {
           "avoidInbreeding": true,
           "maxPairings": 10,
           "preferLocalCows": true
         },
         "page": 0,
         "size": 20
       }
       
       Returns: {
         "success": true,
         "data": [
           {
             "score": 95.5,
             "cow": {
               "id": 123,
               "name": "Bessie",
               "registrationNumber": "CZ-001-2026-00123",
               "attributes": {...},
               "farm": {...},
               "distance": 15.3
             },
             "bull": {
               "id": 456,
               "name": "Thunder",
               "registrationNumber": "CZ-002-2026-00501",
               "attributes": {...},
               "farm": {...},
               "distance": 42.7
             },
             "predictedOffspring": {
               "breed": "Holstein",
               "estimated_weight": 750,
               "estimated_height": 160,
               "genetic_markers": "A2A2 Beta-casein (100% probability)",
               "milk_production_potential": 32.5
             },
             "matchReasoning": {
               "breedCompatibility": 100,
               "geneticDiversity": 95,
               "attributeMatch": 93,
               "locationFeasibility": 85
             }
           },
           ...
         ],
         "pagination": {...}
       }
       
       Algorithm considers:
       - Genetic compatibility and diversity (avoid inbreeding)
       - Mendelian inheritance patterns for attributes
       - Parent attribute averaging/dominance for numeric traits
       - Distance feasibility for both cow and bull
       - Availability of both animals
       - Historical breeding success rates (future enhancement)
```

#### Appointments
```
GET    /api/v1/appointments
       Query params: page, size, status, appointmentType, date, livestockId
       
POST   /api/v1/appointments
       Body: {
         "livestockId": 123,
         "appointmentType": "INSEMINATION",
         "scheduledDate": "2026-07-15",
         "scheduledTime": "10:00",
         "durationMinutes": 60,
         "assigneeId": 45,
         "notes": "Preferred morning slot"
       }

PUT    /api/v1/appointments/{id}
       Body: Partial update

PUT    /api/v1/appointments/{id}/confirm
       Changes status to CONFIRMED

PUT    /api/v1/appointments/{id}/complete
       Changes status to COMPLETED

PUT    /api/v1/appointments/{id}/cancel
       Body: {"cancellationReason": "Farmer unavailable"}
       Changes status to CANCELLED

GET    /api/v1/appointments/calendar
       Query params: startDate, endDate, assigneeId
       Returns: Calendar view of appointments
```

#### Insemination Management
```
POST   /api/v1/inseminations
       Body: {
         "cowId": 123,
         "bullId": 456, // or null if external
         "externalBullInfo": {
           "registrationNumber": "DE-789",
           "breed": "Angus",
           "ownerName": "External Farm GmbH"
         },
         "inseminationDate": "2026-07-10",
         "inseminationTime": "14:30",
         "method": "ARTIFICIAL",
         "performedById": 78,
         "notes": "First attempt"
       }

GET    /api/v1/inseminations/{id}

PUT    /api/v1/inseminations/{id}/confirm-pregnancy
       Body: {
         "pregnancyConfirmed": true,
         "confirmedDate": "2026-08-15",
         "veterinarianId": 90
       }
       Triggers: 
       - Update cow pregnancy status
       - Calculate expected calving date (+ 283 days)
       - Mark cow as unavailable for breeding

GET    /api/v1/inseminations/livestock/{livestockId}
       Returns: Insemination history for specific livestock

PUT    /api/v1/inseminations/{id}/record-calving
       Body: {
         "actualCalvingDate": "2027-04-20",
         "calfInfo": {
           "sex": "FEMALE",
           "weight": 35.0,
           "status": "HEALTHY"
         }
       }
       Triggers:
       - Update cow pregnancy status to CALVED
       - Mark cow available for breeding after recovery period
       - Optionally create calf record
```

#### Health Records
```
GET    /api/v1/health-records
       Query params: livestockId, recordType, dateFrom, dateTo
       
POST   /api/v1/health-records
       Body: {
         "livestockId": 123,
         "recordType": "CHECKUP",
         "recordDate": "2026-07-05",
         "veterinarianId": 90,
         "diagnosis": "Healthy, minor hoof issue",
         "treatment": "Trimmed hooves, applied antiseptic",
         "medications": [
           {"name": "Antiseptic spray", "dosage": "Applied topically"}
         ],
         "followUpRequired": true,
         "followUpDate": "2026-08-05"
       }

GET    /api/v1/health-records/{id}

PUT    /api/v1/health-records/{id}
```

#### Import/Export

**Livestock Import/Export:**
```
POST   /api/v1/import/livestock/batch
       Content-Type: multipart/form-data
       Field: file (CSV or Excel)
       Query params: skipDuplicates, continueOnError
       
       Response: {
         "success": true,
         "data": {
           "totalRows": 150,
           "successCount": 145,
           "errorCount": 5,
           "errors": [
             {"row": 23, "error": "Invalid weight value"},
             {"row": 67, "error": "Duplicate registration number"}
           ]
         }
       }

GET    /api/v1/export/livestock/batch
       Query params: format (csv|excel|json), filters (same as search)
       Returns: File download

POST   /api/v1/import/livestock/single
       Body: Same as POST /api/v1/livestock
```

**Attribute Definition Import:**
```
POST   /api/v1/admin/attributes/import
       Content-Type: multipart/form-data
       Field: file (CSV or JSON)
       Query params: replaceExisting (true|false), preview (true|false)
       
       Preview mode returns proposed changes without applying:
       {
         "newAttributes": [...],
         "updatedAttributes": [...],
         "conflicts": [...]
       }

GET    /api/v1/admin/attributes/export
       Returns: CSV or JSON of all attribute definitions
```

#### Attribute Management
```
GET    /api/v1/attributes/definitions
       Query params: livestockTypeId, isSearchable, isActive
       Returns: List of attribute definitions for form generation

POST   /api/v1/admin/attributes/definitions
       Body: {
         "livestockTypeId": 1,
         "attributeKey": "pedigree_score",
         "attributeName": "Pedigree Score",
         "dataType": "NUMBER",
         "isRequired": false,
         "isSearchable": true,
         "validationRules": {"min": 0, "max": 100}
       }

PUT    /api/v1/admin/attributes/definitions/{id}

DELETE /api/v1/admin/attributes/definitions/{id}
       Soft delete (sets is_active=false)
```

#### Farm Management
```
GET    /api/v1/farms
POST   /api/v1/farms
GET    /api/v1/farms/{id}
PUT    /api/v1/farms/{id}
DELETE /api/v1/farms/{id}
```

#### User Management (Admin only)
```
GET    /api/v1/admin/users
POST   /api/v1/admin/users
GET    /api/v1/admin/users/{id}
PUT    /api/v1/admin/users/{id}
DELETE /api/v1/admin/users/{id}
```

---

## 6. User Interface Requirements

### Design Principles
- **Simplicity:** Clean, uncluttered layouts with Bootstrap 5 components
- **Readability:** Large fonts, high contrast, generous spacing
- **Responsiveness:** Mobile-friendly (farmers may use tablets in field)
- **Performance:** Fast page loads, optimized images, minimal JavaScript

### Key Screens

#### 1. Dashboard (Post-Login)
**For JZD Admin:**
- Statistics cards: Total livestock, Active farms, Pending appointments
- Recent activity feed
- Quick actions: Register livestock, Add farm, Create user

**For Sperm Collector / Inseminator:**
- Search shortcut
- Upcoming appointments
- Recent searches saved

**For Farm Owner:**
- My livestock list
- Pregnancy alerts (approaching calving dates)
- Upcoming appointments

**For Veterinarian:**
- My appointments today/this week
- Pending pregnancy confirmations
- Health follow-ups due

#### 2. Livestock Search/Browse Interface

**Search Mode Toggle (Top):**
- **Tab 1: Browse Livestock** - Direct search for cows or bulls
- **Tab 2: Breeding Match Planner** - Find optimal cow+bull pairings for desired offspring (see section 2b)

**Layout (Browse Mode):**
- **Top:** Search bar with "Quick Search" (name, registration number)
- **Left Sidebar (25%):** Filters panel
  - Livestock type (tabs: Cows, Bulls, Oxen)
  - Sex (radio: Male, Female, Any) - **Bidirectional search enabled**
  - Availability for breeding (checkbox)
  - Location filter (radius search with map picker)
  - Dynamic attribute filters (generated from attribute definitions)
    - Sliders for numeric ranges (weight, height, leg length)
    - Dropdowns for enums (breed, coat color)
    - Date pickers for dates (birth date range)
- **Main Area (75%):** Results display
  - View toggle: Grid / List / Map
  - Sort dropdown: Name, Registration #, Weight, Distance
  - Results count

**Grid View (Default):**
- Card layout: 3-4 cards per row
- Each card shows:
  - Primary photo (square thumbnail)
  - Name + Registration number
  - Key attributes: Breed, Age, Weight
  - Location: Farm name, Distance (if location search)
  - Status badge: Available / Pregnant / Unavailable
  - Quick actions: View Details, Schedule Viewing

**List View:**
- Table with columns: Photo, Name, Registration #, Type, Breed, Age, Weight, Farm, Status
- Row click → Detail page

**Map View:**
- Leaflet map with clustered markers
- Marker popup: Photo, Name, Breed, Distance
- Click popup → Detail page

**Saved Searches:**
- "Save this search" button
- Dropdown to load saved searches

#### 2b. Breeding Match Planner (Outcome-Based Search)

**Purpose:** Find optimal cow+bull pairings to achieve desired calf attributes.

**Layout:**
- **Left Panel (30%):** Desired Offspring Criteria
  - Section header: "What attributes do you want in the calf?"
  - Dynamic attribute inputs (same as livestock registration form)
  - Examples:
    - Breed: Holstein (dropdown)
    - Target weight: 700-800 kg (range slider)
    - Target height: 155-165 cm (range slider)
    - Genetic markers: A2A2 Beta-casein (text input)
    - Milk production: min 30 liters/day (numeric input)
  - Location constraints:
    - Search radius (km slider)
    - Center point (map picker or current location)
  - Advanced options (collapsible):
    - Avoid inbreeding (checkbox, default: true)
    - Prefer local cows (checkbox)
    - Maximum pairs to show (default: 10)
  - "Find Matches" button

- **Right Panel (70%):** Pairing Results
  - Sort by: Match Score, Distance, Genetic Diversity
  - Results displayed as pairing cards:
  
  **Pairing Card:**
  ```
  ┌─────────────────────────────────────────────────────────────┐
  │ Match Score: 95.5%                      🏆 Recommended       │
  ├─────────────────────────────────────────────────────────────┤
  │                                                               │
  │  COW                           +        BULL                 │
  │  ┌──────────────┐                      ┌──────────────┐      │
  │  │  [Photo]     │                      │  [Photo]     │      │
  │  │              │                      │              │      │
  │  └──────────────┘                      └──────────────┘      │
  │  Bessie                                Thunder               │
  │  CZ-001-2026-00123                     CZ-002-2026-00501     │
  │  Holstein, 650kg, 152cm                Angus, 980kg, 165cm   │
  │  📍 Green Valley Farm (15.3 km)        📍 Mountain Farm (42.7 km) │
  │                                                               │
  │  PREDICTED OFFSPRING:                                        │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │ • Breed: Holstein-Angus Cross                         │  │
  │  │ • Estimated weight: ~750 kg ✓ (within target)        │  │
  │  │ • Estimated height: ~160 cm ✓ (within target)        │  │
  │  │ • Genetic markers: A2A2 Beta-casein (100% probability)│  │
  │  │ • Milk production potential: ~32.5 liters/day ✓       │  │
  │  └───────────────────────────────────────────────────────┘  │
  │                                                               │
  │  MATCH REASONING:                                            │
  │  ▓▓▓▓▓▓▓▓▓▓ Breed Compatibility: 100%                       │
  │  ▓▓▓▓▓▓▓▓▓░ Genetic Diversity: 95%                          │
  │  ▓▓▓▓▓▓▓▓▓░ Attribute Match: 93%                            │
  │  ▓▓▓▓▓▓▓▓░░ Location Feasibility: 85%                       │
  │                                                               │
  │  [View Cow Details] [View Bull Details] [Schedule Insemination]│
  └─────────────────────────────────────────────────────────────┘
  ```

**Interaction Flow:**
1. User specifies desired calf attributes
2. User sets location and constraints
3. Clicks "Find Matches"
4. Backend algorithm:
   - Queries available cows and bulls in radius
   - Calculates genetic predictions for all possible pairings
   - Scores pairings based on criteria
   - Returns top N matches sorted by score
5. User reviews pairing cards with predictions
6. User can view individual animal details
7. User can directly schedule insemination from pairing card

**Genetic Prediction Algorithm (Backend):**
- Simple model for numeric traits: offspring = (mother + father) / 2 ± variation
- Mendelian inheritance for genetic markers (dominant/recessive)
- Breed compatibility scoring (purebred vs. crossbred)
- Inbreeding coefficient calculation (if pedigree data available)
- Attribute matching: score each predicted attribute against target range

**Future Enhancements:**
- Machine learning model trained on historical outcomes
- Pedigree analysis for deeper genetic insights
- Multi-generational predictions
- Integration with official breed registry genetic databases

#### 3. Livestock Detail Page

**Header:**
- Breadcrumb: Home > Search > Livestock Detail
- Primary photo (large, 600x600px)
- Name (h1) + Registration number
- Status badges: Available for Breeding / Pregnant / Calving Soon

**Photo Carousel:**
- All photos as thumbnails below primary
- Click to enlarge (lightbox)

**Tabs:**

**Tab 1: Details**
- Basic Info card:
  - Type, Sex, Status
  - Farm name (link)
  - Owner name
- Attributes card:
  - Dynamic key-value pairs from JSONB
  - Grouped logically (Physical, Genetic, Production)
- Location card:
  - Map showing farm location
  - Address

**Tab 2: Insemination History** (for cows)
- Table: Date, Bull, Method, Status, Pregnancy Confirmed
- "Record New Insemination" button (if available)

**Tab 3: Health Records**
- Timeline view of health records
- Expandable items showing diagnosis, treatment, medications
- "Add Health Record" button (vets only)

**Tab 4: Appointments**
- Upcoming appointments table
- Past appointments (collapsed)
- "Schedule Appointment" button

**Actions Panel (Right Sidebar):**
- Schedule Viewing
- Schedule Insemination (if available for breeding)
- Edit Livestock (owner/admin only)
- Upload Photo (owner/admin only)
- Mark as Sold/Deceased (owner/admin only)

#### 4. Register Livestock Form (Multi-Step Wizard)

**Step 1: Basic Information**
- Farm selection (dropdown)
- Livestock type (radio: Cow, Bull, Ox)
- Registration number (auto-generate option)
- Name
- Sex (radio: Male, Female)
- Status (default: Active)

**Step 2: Attributes**
- Dynamic form generated from attribute definitions
- Grouped by category
- Required fields marked with *
- Inline validation (min/max, enums)

**Step 3: Photos**
- Drag-and-drop upload area (Dropzone.js)
- Multiple files allowed
- Preview thumbnails
- Select primary photo (radio buttons)

**Step 4: Review & Submit**
- Summary of all entered data
- "Edit" links to go back to each step
- "Submit" button → POST /api/v1/livestock

**Success:**
- Redirect to livestock detail page
- Success toast notification

#### 5. Appointment Scheduler

**Calendar View (Default):**
- Weekly calendar with time slots (8 AM - 6 PM)
- Click time slot → Create appointment modal
- Existing appointments shown as blocks with color coding:
  - Green: Confirmed
  - Yellow: Scheduled
  - Gray: Completed
  - Red: Cancelled

**Create Appointment Modal:**
- Livestock search/selection
- Appointment type (radio: Viewing, Insemination, Checkup)
- Date picker
- Time picker
- Duration (default 60 min)
- Assignee selection (filtered by role)
- Notes textarea
- "Schedule" button

**My Appointments (List View):**
- Table: Date, Time, Livestock, Type, Status, Farm, Actions
- Filter: Date range, Status, Type
- Actions: Confirm, Complete, Cancel, Reschedule

#### 6. Record Insemination

**Form:**
- Cow selection (search with autocomplete)
- Validate: Female, Available for breeding, Not pregnant
- Bull selection (radio: From database / External)
  - If database: Search bull
  - If external: Enter external bull info (registration #, breed, owner)
- Insemination date & time
- Method (radio: Artificial, Natural)
- Performed by (user selection)
- Notes

**Submit:**
- Creates insemination record with status=PENDING
- Does NOT mark cow as pregnant yet
- Redirects to insemination detail page

#### 7. Confirm Pregnancy (Vet Only)

**Accessed from:**
- Insemination detail page
- Dashboard "Pending confirmations" widget

**Form:**
- Insemination record details (read-only)
- Pregnancy confirmed (radio: Yes, No)
- Confirmation date
- Notes

**Submit (if Yes):**
- Updates insemination record: status=CONFIRMED, pregnancy_confirmed=true
- Updates cow:
  - pregnancy_status=PREGNANT
  - pregnancy_start_date=insemination_date
  - expected_calving_date=insemination_date + 283 days
  - is_available_for_breeding=false
- Sends notification to farm owner

#### 8. Admin - Attribute Manager

**List View:**
- Table: Livestock Type, Attribute Key, Name, Data Type, Required, Searchable, Active
- Filter by livestock type
- Search by attribute name
- "Import Attributes" button
- "Add Attribute" button

**Add/Edit Form:**
- Livestock type (dropdown)
- Attribute key (slug, auto-generated from name)
- Attribute name
- Data type (dropdown: STRING, NUMBER, DECIMAL, BOOLEAN, DATE, ENUM)
- Unit (conditional, shown for numeric types)
- Is required (checkbox)
- Is searchable (checkbox)
- Display order (number)
- **Conditional fields based on data type:**
  - If ENUM: Enum values (textarea, one per line or comma-separated)
  - If NUMBER/DECIMAL: Validation rules (min, max)
  - If STRING: Pattern (regex)

**Import Attributes:**
- File upload (CSV or JSON)
- Preview mode checkbox
- Upload button
- **Preview table shows:**
  - New attributes (green highlight)
  - Updated attributes (yellow highlight)
  - Conflicts (red highlight with warning)
- "Apply Changes" button (if preview mode)

---

## 7. Security & Access Control

### Authentication

**JWT-based authentication:**
- Access token: 1 hour expiry, signed with HS256
- Refresh token: 7 days expiry, stored in database with revocation support
- Password requirements: min 8 characters, uppercase, lowercase, number
- Password hashing: BCrypt with strength 12

**Login flow:**
1. POST /api/v1/auth/login {username, password}
2. Validate credentials
3. Return {accessToken, refreshToken, user}
4. Frontend stores tokens (HttpOnly cookies recommended)

**Token refresh:**
1. POST /api/v1/auth/refresh {refreshToken}
2. Validate refresh token
3. Return new {accessToken}

**Logout:**
1. POST /api/v1/auth/logout {refreshToken}
2. Revoke refresh token in database
3. Frontend clears tokens

### Authorization (Role-Based Access Control)

**Roles and Permissions:**

| Role | Permissions |
|------|-------------|
| **JZD_ADMIN** | - Full access to all JZD data<br>- Manage users within JZD<br>- Register livestock<br>- Manage farms<br>- View all appointments/inseminations<br>- Import/export data |
| **FARM_OWNER** | - Manage own livestock<br>- View own farms<br>- Schedule appointments for own livestock<br>- View insemination history<br>- Upload photos<br>- Record health events (basic) |
| **SPERM_COLLECTOR** | - Search/browse all livestock (read-only)<br>- View livestock details<br>- Schedule viewing appointments<br>- View own appointments |
| **INSEMINATOR** | - Search/browse all livestock (read-only)<br>- Schedule insemination appointments<br>- Record inseminations<br>- View insemination history<br>- Update appointment status |
| **VETERINARIAN** | - Search/browse all livestock (read-only)<br>- View/create health records<br>- Confirm pregnancies<br>- Schedule checkup appointments<br>- View full medical history |

**Method-level security (Spring Security annotations):**
```java
@PreAuthorize("hasAnyRole('JZD_ADMIN', 'FARM_OWNER')")
public Livestock createLivestock(LivestockDto dto) { ... }

@PreAuthorize("hasRole('VETERINARIAN')")
public void confirmPregnancy(Long inseminationId, PregnancyConfirmationDto dto) { ... }

@PreAuthorize("@securityService.canAccessLivestock(#id)")
public Livestock getLivestock(Long id) { ... }
```

### Multi-Tenancy Enforcement

**JzdContextFilter:**
```java
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class JzdContextFilter extends OncePerRequestFilter {
    
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
                                     HttpServletResponse response, 
                                     FilterChain filterChain) 
            throws ServletException, IOException {
        
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        
        if (auth != null && auth.getPrincipal() instanceof UserPrincipal) {
            UserPrincipal principal = (UserPrincipal) auth.getPrincipal();
            JzdContextHolder.setJzdId(principal.getJzdId());
        }
        
        try {
            filterChain.doFilter(request, response);
        } finally {
            JzdContextHolder.clear();
        }
    }
}
```

**Repository-level enforcement:**
```java
public interface LivestockRepository extends JpaRepository<Livestock, Long> {
    
    @Query("SELECT l FROM Livestock l WHERE l.id = :id AND l.jzd.id = :jzdId")
    Optional<Livestock> findByIdAndJzdId(@Param("id") Long id, 
                                         @Param("jzdId") Long jzdId);
    
    // For cross-JZD search (regional platform requirement)
    @Query("SELECT l FROM Livestock l WHERE " +
           "(:livestockTypeId IS NULL OR l.livestockType.id = :livestockTypeId) AND " +
           "(:availableForBreeding IS NULL OR l.isAvailableForBreeding = :availableForBreeding)")
    Page<Livestock> searchAcrossJzds(@Param("livestockTypeId") Long livestockTypeId,
                                      @Param("availableForBreeding") Boolean availableForBreeding,
                                      Pageable pageable);
}
```

**Important:** Regional platform allows cross-JZD search for breeding, but modifications (edit, delete) are restricted to own JZD.

### Data Privacy

- Personal data (user emails, phones) encrypted at rest
- Audit logging for sensitive operations (create user, delete livestock, confirm pregnancy)
- GDPR compliance: User data export, right to be forgotten
- Photo access control: Pre-signed URLs with 7-day expiry

---

## 8. Pregnancy & Availability Tracking

### Business Logic

#### Eligibility for Breeding (Cow)

A cow is available for breeding if ALL conditions are met:
```java
public boolean isEligibleForBreeding(Livestock cow) {
    // Must be female
    if (!"FEMALE".equals(cow.getSex())) return false;
    
    // Must be active
    if (!"ACTIVE".equals(cow.getStatus())) return false;
    
    // Must not be pregnant
    if ("PREGNANT".equals(cow.getPregnancyStatus())) return false;
    
    // Must meet minimum age (15 months)
    LocalDate birthDate = cow.getAttributes().getBirthDate();
    if (birthDate != null && ChronoUnit.MONTHS.between(birthDate, LocalDate.now()) < 15) {
        return false;
    }
    
    // Must not be in post-calving recovery period (60 days)
    if (cow.getActualCalvingDate() != null) {
        long daysSinceCalving = ChronoUnit.DAYS.between(
            cow.getActualCalvingDate(), 
            LocalDate.now()
        );
        if (daysSinceCalving < 60) return false;
    }
    
    // Check for recent health flags (optional)
    // e.g., recent illness requiring recovery
    
    return true;
}
```

#### Record Insemination

```java
@Transactional
public InseminationRecord recordInsemination(InseminationDto dto) {
    Livestock cow = livestockRepository.findById(dto.getCowId())
        .orElseThrow(() -> new NotFoundException("Cow not found"));
    
    // Validate eligibility
    if (!isEligibleForBreeding(cow)) {
        throw new ValidationException("Cow is not eligible for breeding");
    }
    
    // Create record with PENDING status
    InseminationRecord record = new InseminationRecord();
    record.setCow(cow);
    record.setBull(dto.getBullId() != null ? 
        livestockRepository.findById(dto.getBullId()).orElse(null) : null);
    record.setExternalBullInfo(dto.getExternalBullInfo());
    record.setInseminationDate(dto.getInseminationDate());
    record.setMethod(dto.getMethod());
    record.setStatus(InseminationStatus.PENDING);
    record.setPerformedBy(userRepository.findById(dto.getPerformedById()).orElse(null));
    
    // Do NOT mark cow as pregnant yet
    
    return inseminationRepository.save(record);
}
```

#### Confirm Pregnancy

```java
@Transactional
public void confirmPregnancy(Long inseminationId, PregnancyConfirmationDto dto) {
    InseminationRecord record = inseminationRepository.findById(inseminationId)
        .orElseThrow(() -> new NotFoundException("Insemination record not found"));
    
    Livestock cow = record.getCow();
    
    if (dto.isPregnancyConfirmed()) {
        // Update insemination record
        record.setStatus(InseminationStatus.CONFIRMED);
        record.setPregnancyConfirmed(true);
        record.setPregnancyConfirmedDate(dto.getConfirmedDate());
        record.setPregnancyConfirmedBy(dto.getVeterinarianId());
        
        // Update cow pregnancy status
        cow.setPregnancyStatus(PregnancyStatus.PREGNANT);
        cow.setPregnancyStartDate(record.getInseminationDate());
        
        // Calculate expected calving date (cattle gestation: 283 days)
        cow.setExpectedCalvingDate(
            record.getInseminationDate().plusDays(283)
        );
        
        // Mark as unavailable for breeding
        cow.setIsAvailableForBreeding(false);
        
        livestockRepository.save(cow);
        
        // Send notification to farm owner
        notificationService.sendPregnancyConfirmation(cow, record);
    } else {
        // Pregnancy failed
        record.setStatus(InseminationStatus.FAILED);
        record.setPregnancyConfirmed(false);
        // Cow remains available for breeding
    }
    
    inseminationRepository.save(record);
}
```

#### Record Calving

```java
@Transactional
public void recordCalving(Long inseminationId, CalvingDto dto) {
    InseminationRecord record = inseminationRepository.findById(inseminationId)
        .orElseThrow(() -> new NotFoundException("Insemination record not found"));
    
    Livestock cow = record.getCow();
    
    // Update cow status
    cow.setPregnancyStatus(PregnancyStatus.CALVED);
    cow.setActualCalvingDate(dto.getCalvingDate());
    
    // Recovery period: mark available after 60 days
    // For now, keep unavailable; scheduled job will update after recovery
    cow.setIsAvailableForBreeding(false);
    
    livestockRepository.save(cow);
    
    // Create health record for calving event
    HealthRecord healthRecord = new HealthRecord();
    healthRecord.setLivestock(cow);
    healthRecord.setRecordType(HealthRecordType.CALVING);
    healthRecord.setRecordDate(dto.getCalvingDate());
    healthRecord.setNotes("Calving recorded. Calf: " + dto.getCalfInfo());
    healthRecordRepository.save(healthRecord);
    
    // Optionally create calf record
    if (dto.isCreateCalfRecord()) {
        Livestock calf = new Livestock();
        calf.setFarm(cow.getFarm());
        calf.setJzd(cow.getJzd());
        calf.setLivestockType(cow.getLivestockType());
        calf.setSex(dto.getCalfSex());
        calf.setStatus(LivestockStatus.ACTIVE);
        calf.getAttributes().put("birth_date", dto.getCalvingDate());
        calf.getAttributes().put("birth_weight", dto.getCalfWeight());
        calf.getAttributes().put("mother_id", cow.getId());
        if (record.getBull() != null) {
            calf.getAttributes().put("father_id", record.getBull().getId());
        }
        livestockRepository.save(calf);
    }
    
    // Notification
    notificationService.sendCalvingNotification(cow, dto);
}
```

### Scheduled Jobs

**Daily Pregnancy Status Update Job (Runs 1:00 AM):**
```java
@Scheduled(cron = "0 0 1 * * *") // Daily at 1 AM
@Transactional
public void updatePregnancyStatuses() {
    LocalDate today = LocalDate.now();
    
    // Find cows approaching calving (within 7 days)
    List<Livestock> approachingCalving = livestockRepository
        .findByPregnancyStatusAndExpectedCalvingDateBetween(
            PregnancyStatus.PREGNANT,
            today,
            today.plusDays(7)
        );
    
    for (Livestock cow : approachingCalving) {
        notificationService.sendApproachingCalvingAlert(cow);
    }
    
    // Find overdue pregnancies (> 7 days past expected date)
    List<Livestock> overdue = livestockRepository
        .findByPregnancyStatusAndExpectedCalvingDateBefore(
            PregnancyStatus.PREGNANT,
            today.minusDays(7)
        );
    
    for (Livestock cow : overdue) {
        notificationService.sendOverduePregnancyAlert(cow);
    }
    
    // Update cows past recovery period (60 days after calving)
    List<Livestock> recovered = livestockRepository
        .findByPregnancyStatusAndActualCalvingDateBefore(
            PregnancyStatus.CALVED,
            today.minusDays(60)
        );
    
    for (Livestock cow : recovered) {
        if (isEligibleForBreeding(cow)) {
            cow.setIsAvailableForBreeding(true);
            livestockRepository.save(cow);
            notificationService.sendAvailableForBreedingNotification(cow);
        }
    }
}
```

---

## 9. Location & Geography

### Storage

**Database schema:**
```sql
-- Farms and JZDs store coordinates
ALTER TABLE farm ADD COLUMN latitude DECIMAL(10, 8) NOT NULL;
ALTER TABLE farm ADD COLUMN longitude DECIMAL(11, 8) NOT NULL;

-- Optional: PostGIS for advanced spatial queries
CREATE EXTENSION IF NOT EXISTS postgis;
ALTER TABLE farm ADD COLUMN geom GEOMETRY(Point, 4326);

-- Spatial index
CREATE INDEX idx_farm_geom ON farm USING GIST(geom);
```

### Radius Search

**Using PostGIS (recommended for production):**
```java
@Query(value = "SELECT l.* FROM livestock l " +
       "JOIN farm f ON l.farm_id = f.id " +
       "WHERE ST_DWithin(" +
       "  f.geom::geography, " +
       "  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, " +
       "  :radiusMeters" +
       ") " +
       "AND l.livestock_type_id = :typeId " +
       "AND l.is_available_for_breeding = true",
       nativeQuery = true)
List<Livestock> findWithinRadius(@Param("lat") double latitude,
                                  @Param("lon") double longitude,
                                  @Param("radiusMeters") double radiusMeters,
                                  @Param("typeId") Long livestockTypeId);
```

**Using Haversine formula (fallback without PostGIS):**
```java
@Query("SELECT l FROM Livestock l JOIN l.farm f WHERE " +
       "l.livestockType.id = :typeId AND " +
       "l.isAvailableForBreeding = true AND " +
       "(6371 * acos(cos(radians(:lat)) * cos(radians(f.latitude)) * " +
       "cos(radians(f.longitude) - radians(:lon)) + " +
       "sin(radians(:lat)) * sin(radians(f.latitude)))) <= :radiusKm")
List<Livestock> findWithinRadiusHaversine(@Param("lat") double latitude,
                                           @Param("lon") double longitude,
                                           @Param("radiusKm") double radiusKm,
                                           @Param("typeId") Long livestockTypeId);
```

### Map UI

**Frontend implementation (Leaflet.js):**
```javascript
// Initialize map
const map = L.map('map').setView([50.0755, 14.4378], 8); // Prague, CZ

// OpenStreetMap tiles
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// Add livestock markers
fetch('/api/v1/search/livestock', {
    method: 'POST',
    body: JSON.stringify(searchCriteria)
})
.then(response => response.json())
.then(data => {
    const markers = L.markerClusterGroup(); // Cluster markers
    
    data.data.forEach(livestock => {
        const marker = L.marker([livestock.farm.latitude, livestock.farm.longitude])
            .bindPopup(`
                <div class="livestock-popup">
                    <img src="${livestock.primaryPhoto}" width="100">
                    <h6>${livestock.name}</h6>
                    <p>${livestock.attributes.breed} - ${livestock.attributes.weight}kg</p>
                    <p><strong>Distance:</strong> ${livestock.distance.toFixed(1)} km</p>
                    <a href="/livestock/${livestock.id}">View Details</a>
                </div>
            `);
        markers.addLayer(marker);
    });
    
    map.addLayer(markers);
});

// Draw search radius circle
const searchLocation = [50.0755, 14.4378];
const radiusKm = 50;
L.circle(searchLocation, {
    radius: radiusKm * 1000, // Convert to meters
    color: 'blue',
    fillColor: '#3388ff',
    fillOpacity: 0.1
}).addTo(map);
```

### Geocoding

**Address to Coordinates:**
- Use Nominatim (OpenStreetMap) API for free geocoding
- Cache results in Redis (key: address hash, TTL: 30 days)
- Fallback to Google Maps Geocoding API if budget allows

```java
@Service
public class GeocodingService {
    
    @Cacheable(value = "geocode", key = "#address")
    public Coordinates geocode(String address) {
        // Try Nominatim first
        try {
            String url = "https://nominatim.openstreetmap.org/search?q=" +
                         URLEncoder.encode(address, "UTF-8") +
                         "&format=json&limit=1";
            
            // HTTP request...
            // Parse JSON response
            // Return Coordinates(lat, lon)
        } catch (Exception e) {
            log.error("Geocoding failed", e);
            return null;
        }
    }
}
```

---

## 10. Photo & Media Storage

### Architecture

**Storage Backend:** AWS S3 or MinIO (S3-compatible, self-hosted)

**Bucket structure:**
```
livestock-photos-production/
  ├── {jzd_id}/
  │   ├── {livestock_id}/
  │   │   ├── {timestamp}_{original_filename}.jpg
  │   │   ├── {timestamp}_{original_filename}_thumb.jpg
```

**Example object key:**
```
42/1523/1719482736_bessie_profile.jpg
42/1523/1719482736_bessie_profile_thumb.jpg
```

### Upload Flow

**1. Frontend initiates upload:**
```javascript
// Using Dropzone.js
const myDropzone = new Dropzone("#photo-upload", {
    url: "/api/v1/livestock/1523/photos",
    paramName: "photo",
    maxFilesize: 5, // MB
    acceptedFiles: "image/jpeg,image/png",
    headers: {
        "Authorization": "Bearer " + accessToken
    }
});

myDropzone.on("success", function(file, response) {
    console.log("Upload successful:", response.data.url);
});
```

**2. Backend handles upload:**
```java
@PostMapping("/{id}/photos")
public ResponseEntity<?> uploadPhoto(@PathVariable Long id,
                                     @RequestParam("photo") MultipartFile file,
                                     @RequestParam(defaultValue = "false") boolean isPrimary) {
    
    // Validate file
    if (file.getSize() > 5 * 1024 * 1024) {
        throw new ValidationException("File size exceeds 5MB");
    }
    
    String contentType = file.getContentType();
    if (!contentType.equals("image/jpeg") && !contentType.equals("image/png")) {
        throw new ValidationException("Only JPEG and PNG images allowed");
    }
    
    // Get livestock
    Livestock livestock = livestockRepository.findByIdAndJzdId(id, JzdContextHolder.getJzdId())
        .orElseThrow(() -> new NotFoundException("Livestock not found"));
    
    // Generate unique filename
    String timestamp = String.valueOf(System.currentTimeMillis());
    String extension = contentType.equals("image/jpeg") ? "jpg" : "png";
    String filename = timestamp + "_" + sanitizeFilename(file.getOriginalFilename());
    
    // S3 object key
    String objectKey = String.format("%d/%d/%s", 
        livestock.getJzd().getId(),
        livestock.getId(),
        filename
    );
    
    // Upload to S3
    s3Client.putObject(PutObjectRequest.builder()
        .bucket("livestock-photos-production")
        .key(objectKey)
        .contentType(contentType)
        .build(),
        RequestBody.fromInputStream(file.getInputStream(), file.getSize()));
    
    // Generate pre-signed URL (7 days expiry)
    String photoUrl = s3Client.utilities().getUrl(builder -> builder
        .bucket("livestock-photos-production")
        .key(objectKey))
        .toString();
    
    // Create photo record
    LivestockPhoto photo = new LivestockPhoto();
    photo.setLivestock(livestock);
    photo.setFileKey(objectKey);
    photo.setFileUrl(photoUrl);
    photo.setFileSize(file.getSize());
    photo.setMimeType(contentType);
    photo.setIsPrimary(isPrimary);
    photo.setUploadedBy(getCurrentUser());
    
    livestockPhotoRepository.save(photo);
    
    // Async thumbnail generation
    thumbnailService.generateThumbnailAsync(objectKey);
    
    return ResponseEntity.ok(new ApiResponse(photo));
}
```

**3. Async thumbnail generation:**
```java
@Async
@Transactional
public void generateThumbnailAsync(String objectKey) {
    try {
        // Download original from S3
        S3Object s3Object = s3Client.getObject(builder -> builder
            .bucket("livestock-photos-production")
            .key(objectKey));
        
        BufferedImage original = ImageIO.read(s3Object);
        
        // Resize to 300x300px
        BufferedImage thumbnail = Scalr.resize(original, 
            Scalr.Method.QUALITY, 
            Scalr.Mode.FIT_TO_WIDTH,
            300, 300);
        
        // Upload thumbnail to S3
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ImageIO.write(thumbnail, "jpg", baos);
        
        String thumbKey = objectKey.replace(".jpg", "_thumb.jpg")
                                   .replace(".png", "_thumb.jpg");
        
        s3Client.putObject(PutObjectRequest.builder()
            .bucket("livestock-photos-production")
            .key(thumbKey)
            .contentType("image/jpeg")
            .build(),
            RequestBody.fromBytes(baos.toByteArray()));
        
        // Update database record
        LivestockPhoto photo = livestockPhotoRepository.findByFileKey(objectKey)
            .orElseThrow();
        photo.setThumbnailUrl(s3Client.utilities().getUrl(builder -> builder
            .bucket("livestock-photos-production")
            .key(thumbKey)).toString());
        livestockPhotoRepository.save(photo);
        
    } catch (Exception e) {
        log.error("Thumbnail generation failed for " + objectKey, e);
    }
}
```

### CDN Integration

**CloudFront (or similar CDN) in front of S3:**
- Distribution domain: `cdn.livestock-platform.cz`
- Cache TTL: 7 days for photos
- Signed URLs for private photos (if needed)
- Automatic compression (WebP format for modern browsers)

**Photo URL in API response:**
```json
{
  "photoUrl": "https://cdn.livestock-platform.cz/42/1523/1719482736_bessie_profile.jpg",
  "thumbnailUrl": "https://cdn.livestock-platform.cz/42/1523/1719482736_bessie_profile_thumb.jpg"
}
```

### Storage Costs Estimation

For 100k users with average 5 photos per livestock:
- 200k livestock × 5 photos = 1M photos
- Average photo size: 2MB
- Average thumbnail: 50KB
- Total: (1M × 2MB) + (1M × 50KB) = ~2.05 TB

**S3 costs (us-east-1):**
- Storage: 2050 GB × $0.023/GB = $47.15/month
- Requests: Negligible
- Data transfer: ~$50-100/month (with CloudFront caching)
- **Total: ~$100-150/month**

**MinIO self-hosted:**
- Storage: 2.5TB SSD = ~$200-300 one-time
- Server costs: Included in app infrastructure
- **Total: $0/month ongoing**

---

## 11. Import/Export System

### Supported Formats

1. **CSV** - Simple, widely supported
2. **Excel (.xlsx)** - User-friendly for non-technical users
3. **JSON** - For API integrations

### Livestock Batch Import

**CSV Format:**
```csv
registration_number,name,livestock_type,farm_id,sex,status,breed,birth_date,weight,height,leg_length,coat_color
CZ-001-2026-00123,Bessie,COW,42,FEMALE,ACTIVE,Holstein,2024-03-15,650.5,152.0,45.2,Black and White
CZ-001-2026-00124,Daisy,COW,42,FEMALE,ACTIVE,Jersey,2023-11-20,580.0,148.5,43.8,Fawn
CZ-002-2026-00501,Thunder,BULL,43,MALE,ACTIVE,Angus,2022-05-10,980.0,165.0,52.0,Black
```

**Import Implementation:**
```java
@PostMapping("/import/livestock/batch")
public ResponseEntity<?> importLivestockBatch(
        @RequestParam("file") MultipartFile file,
        @RequestParam(defaultValue = "false") boolean skipDuplicates,
        @RequestParam(defaultValue = "false") boolean continueOnError) {
    
    if (!file.getContentType().equals("text/csv") && 
        !file.getOriginalFilename().endsWith(".xlsx")) {
        throw new ValidationException("Only CSV and Excel files supported");
    }
    
    ImportResult result = new ImportResult();
    List<ImportError> errors = new ArrayList<>();
    
    try (Reader reader = new InputStreamReader(file.getInputStream())) {
        CSVParser csvParser = new CSVParserBuilder()
            .withSeparator(',')
            .build();
        
        CSVReader csvReader = new CSVReaderBuilder(reader)
            .withCSVParser(csvParser)
            .withSkipLines(1) // Skip header
            .build();
        
        String[] row;
        int rowNumber = 2; // Start from 2 (after header)
        
        while ((row = csvReader.readNext()) != null) {
            try {
                // Parse row
                LivestockDto dto = parseLivestockRow(row);
                
                // Check for duplicates
                if (livestockRepository.existsByRegistrationNumber(dto.getRegistrationNumber())) {
                    if (skipDuplicates) {
                        result.incrementSkipped();
                        continue;
                    } else {
                        throw new ValidationException("Duplicate registration number");
                    }
                }
                
                // Create livestock
                Livestock livestock = livestockService.create(dto);
                result.incrementSuccess();
                
            } catch (Exception e) {
                errors.add(new ImportError(rowNumber, e.getMessage()));
                result.incrementError();
                
                if (!continueOnError) {
                    break; // Stop on first error
                }
            }
            
            rowNumber++;
        }
        
        result.setErrors(errors);
        return ResponseEntity.ok(result);
        
    } catch (Exception e) {
        return ResponseEntity.status(500).body(
            new ApiError("IMPORT_FAILED", "Import failed: " + e.getMessage())
        );
    }
}

private LivestockDto parseLivestockRow(String[] row) {
    LivestockDto dto = new LivestockDto();
    dto.setRegistrationNumber(row[0]);
    dto.setName(row[1]);
    dto.setLivestockType(row[2]);
    dto.setFarmId(Long.parseLong(row[3]));
    dto.setSex(row[4]);
    dto.setStatus(row[5]);
    
    // Parse attributes
    Map<String, Object> attributes = new HashMap<>();
    attributes.put("breed", row[6]);
    attributes.put("birth_date", row[7]);
    attributes.put("weight", Double.parseDouble(row[8]));
    attributes.put("height", Double.parseDouble(row[9]));
    attributes.put("leg_length", Double.parseDouble(row[10]));
    attributes.put("coat_color", row[11]);
    
    dto.setAttributes(attributes);
    return dto;
}
```

**Import Result Response:**
```json
{
  "success": true,
  "data": {
    "totalRows": 150,
    "successCount": 145,
    "errorCount": 5,
    "skippedCount": 0,
    "errors": [
      {
        "row": 23,
        "error": "Invalid weight value: must be between 0 and 2000"
      },
      {
        "row": 67,
        "error": "Duplicate registration number: CZ-001-2026-00099"
      },
      {
        "row": 89,
        "error": "Farm ID 999 not found"
      }
    ]
  }
}
```

### Livestock Batch Export

**Export Implementation:**
```java
@GetMapping("/export/livestock/batch")
public ResponseEntity<Resource> exportLivestockBatch(
        @RequestParam(defaultValue = "csv") String format,
        @RequestParam(required = false) Long livestockTypeId,
        @RequestParam(required = false) Long farmId,
        @RequestParam(required = false) String status) {
    
    // Build query criteria
    LivestockSearchCriteria criteria = LivestockSearchCriteria.builder()
        .livestockTypeId(livestockTypeId)
        .farmId(farmId)
        .status(status)
        .jzdId(JzdContextHolder.getJzdId())
        .build();
    
    List<Livestock> livestockList = livestockRepository.search(criteria);
    
    if ("csv".equals(format)) {
        return exportAsCSV(livestockList);
    } else if ("excel".equals(format)) {
        return exportAsExcel(livestockList);
    } else {
        return exportAsJSON(livestockList);
    }
}

private ResponseEntity<Resource> exportAsCSV(List<Livestock> livestockList) {
    StringWriter writer = new StringWriter();
    CSVWriter csvWriter = new CSVWriter(writer);
    
    // Header
    String[] header = {"registration_number", "name", "livestock_type", 
                       "farm_id", "sex", "status", "breed", "birth_date", 
                       "weight", "height", "leg_length", "coat_color"};
    csvWriter.writeNext(header);
    
    // Data rows
    for (Livestock livestock : livestockList) {
        Map<String, Object> attrs = livestock.getAttributes();
        String[] row = {
            livestock.getRegistrationNumber(),
            livestock.getName(),
            livestock.getLivestockType().getCode(),
            livestock.getFarm().getId().toString(),
            livestock.getSex(),
            livestock.getStatus(),
            attrs.get("breed").toString(),
            attrs.get("birth_date").toString(),
            attrs.get("weight").toString(),
            attrs.get("height").toString(),
            attrs.get("leg_length").toString(),
            attrs.getOrDefault("coat_color", "").toString()
        };
        csvWriter.writeNext(row);
    }
    
    csvWriter.close();
    
    ByteArrayResource resource = new ByteArrayResource(
        writer.toString().getBytes(StandardCharsets.UTF_8)
    );
    
    return ResponseEntity.ok()
        .header(HttpHeaders.CONTENT_DISPOSITION, 
                "attachment; filename=livestock_export_" + 
                LocalDate.now() + ".csv")
        .contentType(MediaType.parseMediaType("text/csv"))
        .body(resource);
}
```

### Attribute Definition Import

**CSV Format:**
```csv
livestock_type,attribute_key,attribute_name,data_type,unit,is_required,is_searchable,enum_values,validation_rules
CATTLE,breed,Breed,ENUM,,true,true,Holstein|Angus|Jersey|Hereford,
CATTLE,weight,Weight,DECIMAL,kg,true,true,,min:0|max:2000
CATTLE,height,Height,DECIMAL,cm,false,true,,min:0|max:200
CATTLE,leg_length,Leg Length,DECIMAL,cm,false,true,,min:0|max:100
CATTLE,birth_date,Birth Date,DATE,,true,true,,
```

**Import with Preview:**
```java
@PostMapping("/admin/attributes/import")
public ResponseEntity<?> importAttributes(
        @RequestParam("file") MultipartFile file,
        @RequestParam(defaultValue = "false") boolean preview,
        @RequestParam(defaultValue = "false") boolean replaceExisting) {
    
    List<AttributeDefinition> newAttributes = new ArrayList<>();
    List<AttributeDefinition> updatedAttributes = new ArrayList<>();
    List<String> conflicts = new ArrayList<>();
    
    try (Reader reader = new InputStreamReader(file.getInputStream())) {
        CSVReader csvReader = new CSVReaderBuilder(reader)
            .withSkipLines(1)
            .build();
        
        String[] row;
        while ((row = csvReader.readNext()) != null) {
            AttributeDefinitionDto dto = parseAttributeRow(row);
            
            // Check if attribute exists
            Optional<AttributeDefinition> existing = 
                attributeRepository.findByLivestockTypeAndKey(
                    dto.getLivestockType(), 
                    dto.getAttributeKey()
                );
            
            if (existing.isPresent()) {
                if (replaceExisting) {
                    AttributeDefinition updated = existing.get();
                    updateAttributeFromDto(updated, dto);
                    updatedAttributes.add(updated);
                } else {
                    conflicts.add(dto.getAttributeKey() + 
                                  " already exists for " + 
                                  dto.getLivestockType());
                }
            } else {
                AttributeDefinition newAttr = createAttributeFromDto(dto);
                newAttributes.add(newAttr);
            }
        }
        
        if (preview) {
            // Return preview without saving
            return ResponseEntity.ok(Map.of(
                "newAttributes", newAttributes,
                "updatedAttributes", updatedAttributes,
                "conflicts", conflicts
            ));
        } else {
            // Save changes
            attributeRepository.saveAll(newAttributes);
            attributeRepository.saveAll(updatedAttributes);
            
            return ResponseEntity.ok(Map.of(
                "newCount", newAttributes.size(),
                "updatedCount", updatedAttributes.size(),
                "conflictCount", conflicts.size()
            ));
        }
        
    } catch (Exception e) {
        return ResponseEntity.status(500).body(
            new ApiError("IMPORT_FAILED", e.getMessage())
        );
    }
}
```

---

## 12. Scalability for 100k Users

### Performance Targets

- **Concurrent users:** 10,000
- **API response time:** < 200ms (p95)
- **Search response time:** < 500ms (p95)
- **Page load time:** < 2s (p95)
- **Uptime:** 99.9% (43 min downtime/month)

### Database Optimization

**1. Connection Pooling (HikariCP):**
```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 50
      minimum-idle: 10
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
```

**2. Read Replicas:**
- 1 primary (writes)
- 2-3 read replicas (search queries, reports)
- Spring Data JPA routing:
```java
@Transactional(readOnly = true)
public Page<Livestock> search(SearchCriteria criteria) {
    // Routes to read replica
}
```

**3. Indexing Strategy:**
```sql
-- Already covered in entity sections
-- Key indexes:
CREATE INDEX idx_livestock_jzd ON livestock(jzd_id);
CREATE INDEX idx_livestock_available ON livestock(is_available_for_breeding);
CREATE INDEX idx_livestock_attributes ON livestock USING GIN(attributes);
CREATE INDEX idx_farm_location ON farm(latitude, longitude);
```

**4. Partitioning (for large tables):**
```sql
-- Partition audit_log by month
CREATE TABLE audit_log (
    id BIGSERIAL,
    created_at TIMESTAMP NOT NULL,
    ...
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_log_2026_06 PARTITION OF audit_log
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
    
-- Partition insemination_record by year
CREATE TABLE insemination_record (
    id BIGSERIAL,
    insemination_date DATE NOT NULL,
    ...
) PARTITION BY RANGE (insemination_date);
```

### Application Tier Scaling

**1. Stateless Instances:**
- 10-20 Spring Boot pods in Kubernetes
- Horizontal Pod Autoscaler (HPA):
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: livestock-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: livestock-api
  minReplicas: 10
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**2. Session Management:**
- Redis-backed sessions (Spring Session)
- Session TTL: 30 minutes
```yaml
spring:
  session:
    store-type: redis
    redis:
      namespace: livestock:session
```

**3. Caching Strategy:**

**Redis cache layers:**
```java
@Cacheable(value = "livestock", key = "#id", unless = "#result == null")
public Livestock findById(Long id) {
    // Cache individual livestock for 5 minutes
}

@Cacheable(value = "searchResults", key = "#criteria.hashCode()", 
           unless = "#result.isEmpty()")
public Page<Livestock> search(SearchCriteria criteria) {
    // Cache search results for 2 minutes
}

@Cacheable(value = "attributeDefinitions", key = "#livestockTypeId")
public List<AttributeDefinition> getDefinitions(Long livestockTypeId) {
    // Cache attribute definitions for 1 hour (rarely change)
}
```

**Cache configuration:**
```yaml
spring:
  cache:
    type: redis
    redis:
      time-to-live: 300000 # 5 minutes default
      cache-null-values: false
  redis:
    host: redis-cluster.livestock.svc.cluster.local
    port: 6379
    lettuce:
      pool:
        max-active: 100
        max-idle: 50
```

### Elasticsearch for Search

**1. Cluster Setup:**
- 3 Elasticsearch nodes
- 5 primary shards, 1 replica each
- Heap size: 8GB per node

**2. Index Mapping:**
```json
PUT /livestock
{
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 1
  },
  "mappings": {
    "properties": {
      "id": {"type": "long"},
      "jzdId": {"type": "long"},
      "registrationNumber": {"type": "keyword"},
      "name": {"type": "text"},
      "livestockTypeId": {"type": "long"},
      "sex": {"type": "keyword"},
      "isAvailableForBreeding": {"type": "boolean"},
      "pregnancyStatus": {"type": "keyword"},
      "farmLocation": {"type": "geo_point"},
      "attributes": {
        "type": "object",
        "dynamic": true
      },
      "updatedAt": {"type": "date"}
    }
  }
}
```

**3. Sync Strategy:**
- Incremental sync every 5 minutes (via scheduled job)
- Track `last_sync_timestamp` in Redis
- Only sync livestock with `updated_at > last_sync_timestamp`

```java
@Scheduled(fixedDelay = 300000) // 5 minutes
@Transactional(readOnly = true)
public void syncToElasticsearch() {
    LocalDateTime lastSync = getLastSyncTimestamp();
    LocalDateTime now = LocalDateTime.now();
    
    List<Livestock> updated = livestockRepository
        .findByUpdatedAtAfter(lastSync);
    
    if (!updated.isEmpty()) {
        elasticsearchService.bulkIndex(updated);
        setLastSyncTimestamp(now);
    }
}
```

**4. Search Query:**
```java
public Page<Livestock> searchElasticsearch(SearchCriteria criteria) {
    BoolQueryBuilder query = QueryBuilders.boolQuery();
    
    // Filters
    if (criteria.getLivestockTypeId() != null) {
        query.filter(QueryBuilders.termQuery("livestockTypeId", 
                                              criteria.getLivestockTypeId()));
    }
    
    if (criteria.getAvailableForBreeding() != null) {
        query.filter(QueryBuilders.termQuery("isAvailableForBreeding", 
                                              criteria.getAvailableForBreeding()));
    }
    
    // Attribute filters
    if (criteria.getAttributeFilters() != null) {
        criteria.getAttributeFilters().forEach((key, value) -> {
            if (value instanceof RangeFilter) {
                RangeFilter range = (RangeFilter) value;
                query.filter(QueryBuilders.rangeQuery("attributes." + key)
                    .gte(range.getMin())
                    .lte(range.getMax()));
            } else {
                query.filter(QueryBuilders.termQuery("attributes." + key, value));
            }
        });
    }
    
    // Location filter (geo_distance)
    if (criteria.getLocation() != null) {
        query.filter(QueryBuilders.geoDistanceQuery("farmLocation")
            .point(criteria.getLocation().getLatitude(), 
                   criteria.getLocation().getLongitude())
            .distance(criteria.getLocation().getRadiusKm(), DistanceUnit.KILOMETERS));
    }
    
    // Execute search
    SearchRequest request = new SearchRequest("livestock")
        .source(new SearchSourceBuilder()
            .query(query)
            .from(criteria.getPage() * criteria.getSize())
            .size(criteria.getSize()));
    
    SearchResponse response = esClient.search(request, RequestOptions.DEFAULT);
    
    // Convert hits to Livestock entities
    List<Long> ids = Arrays.stream(response.getHits().getHits())
        .map(hit -> Long.parseLong(hit.getId()))
        .collect(Collectors.toList());
    
    // Fetch full data from PostgreSQL (or use ES source)
    List<Livestock> results = livestockRepository.findAllById(ids);
    
    return new PageImpl<>(results, 
                          PageRequest.of(criteria.getPage(), criteria.getSize()),
                          response.getHits().getTotalHits().value);
}
```

### Async Processing

**RabbitMQ for background tasks:**
- Photo thumbnail generation
- Elasticsearch indexing
- Email notifications
- Report generation

**Example:**
```java
@Component
public class PhotoUploadListener {
    
    @RabbitListener(queues = "photo-processing")
    public void processPhoto(PhotoUploadEvent event) {
        thumbnailService.generateThumbnail(event.getObjectKey());
        // Re-index livestock in Elasticsearch
        elasticsearchService.indexLivestock(event.getLivestockId());
    }
}

// Producer
@Service
public class LivestockPhotoService {
    
    @Autowired
    private RabbitTemplate rabbitTemplate;
    
    public LivestockPhoto uploadPhoto(MultipartFile file, Long livestockId) {
        // ... upload to S3 ...
        
        // Send to queue for async processing
        rabbitTemplate.convertAndSend("photo-processing", 
            new PhotoUploadEvent(livestockId, objectKey));
        
        return photo;
    }
}
```

### Load Balancing

**NGINX configuration:**
```nginx
upstream livestock-api {
    least_conn;
    server livestock-api-1:8080 max_fails=3 fail_timeout=30s;
    server livestock-api-2:8080 max_fails=3 fail_timeout=30s;
    server livestock-api-3:8080 max_fails=3 fail_timeout=30s;
    # ... up to 20 instances
}

server {
    listen 443 ssl http2;
    server_name api.livestock-platform.cz;
    
    # SSL configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # Timeouts
    proxy_connect_timeout 10s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;
    
    # Request buffering
    client_max_body_size 10M;
    
    location /api/ {
        proxy_pass http://livestock-api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Caching for GET requests
        proxy_cache_methods GET HEAD;
        proxy_cache_key "$scheme$request_method$host$request_uri";
        proxy_cache livestock_cache;
        proxy_cache_valid 200 2m;
    }
    
    location /static/ {
        proxy_pass http://livestock-api;
        proxy_cache livestock_static_cache;
        proxy_cache_valid 200 7d;
    }
}
```

### Monitoring & Alerting

**Prometheus metrics:**
```java
@Component
public class MetricsConfiguration {
    
    @Bean
    public MeterRegistryCustomizer<MeterRegistry> metricsCommonTags() {
        return registry -> registry.config()
            .commonTags("application", "livestock-api");
    }
    
    // Custom metrics
    private Counter searchRequestCounter;
    private Timer searchResponseTime;
    private Gauge activePregnancies;
    
    @Autowired
    public MetricsConfiguration(MeterRegistry registry) {
        this.searchRequestCounter = Counter.builder("search.requests")
            .description("Total search requests")
            .tag("type", "livestock")
            .register(registry);
        
        this.searchResponseTime = Timer.builder("search.response.time")
            .description("Search response time")
            .register(registry);
        
        this.activePregnancies = Gauge.builder("livestock.pregnancies.active", 
                livestockRepository, LivestockRepository::countActivePregnancies)
            .description("Number of active pregnancies")
            .register(registry);
    }
}
```

**Grafana dashboards:**
- API request rate, latency, error rate
- Database connection pool usage
- Redis cache hit rate
- Elasticsearch query performance
- Active users, active pregnancies
- Storage usage (S3)

**Alerts:**
- Error rate > 5% for 5 minutes
- API latency p95 > 500ms for 10 minutes
- Database connection pool > 90% for 5 minutes
- Disk usage > 85%
- Elasticsearch cluster health RED

### Load Testing

**JMeter test plan:**
- 10,000 concurrent users
- Ramp-up: 10 minutes
- Test duration: 30 minutes
- Scenarios:
  - 50% Search queries
  - 20% View livestock details
  - 15% Create appointments
  - 10% Upload photos
  - 5% Admin operations

**Performance acceptance criteria:**
- All requests < 1s response time (p95)
- Error rate < 0.5%
- No database connection pool exhaustion
- No memory leaks

---

## 13. Critical Implementation Files

### Database Migration

**File:** `src/main/resources/db/migration/V001__initial_schema.sql`
- All table definitions from section 3
- Indexes, constraints, foreign keys
- Initial data: livestock types (COW, BULL, OX)
- Initial attribute definitions

### Core Domain Entities

**File:** `src/main/java/com/livestock/management/entity/Livestock.java`
```java
@Entity
@Table(name = "livestock")
public class Livestock {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "jzd_id", nullable = false)
    private Jzd jzd;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "farm_id", nullable = false)
    private Farm farm;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "livestock_type_id", nullable = false)
    private LivestockType livestockType;
    
    @Column(unique = true, nullable = false)
    private String registrationNumber;
    
    private String name;
    
    @Enumerated(EnumType.STRING)
    private Sex sex;
    
    @Enumerated(EnumType.STRING)
    private LivestockStatus status;
    
    @Type(JsonBinaryType.class)
    @Column(columnDefinition = "jsonb", nullable = false)
    private Map<String, Object> attributes = new HashMap<>();
    
    private Boolean isAvailableForBreeding = true;
    
    @Enumerated(EnumType.STRING)
    private PregnancyStatus pregnancyStatus;
    
    private LocalDate pregnancyStartDate;
    private LocalDate expectedCalvingDate;
    private LocalDate actualCalvingDate;
    
    // Business logic methods
    public boolean isEligibleForBreeding() {
        if (sex != Sex.FEMALE) return false;
        if (status != LivestockStatus.ACTIVE) return false;
        if (pregnancyStatus == PregnancyStatus.PREGNANT) return false;
        
        LocalDate birthDate = (LocalDate) attributes.get("birth_date");
        if (birthDate != null && 
            ChronoUnit.MONTHS.between(birthDate, LocalDate.now()) < 15) {
            return false;
        }
        
        if (actualCalvingDate != null && 
            ChronoUnit.DAYS.between(actualCalvingDate, LocalDate.now()) < 60) {
            return false;
        }
        
        return true;
    }
    
    public void markPregnant(LocalDate inseminationDate) {
        this.pregnancyStatus = PregnancyStatus.PREGNANT;
        this.pregnancyStartDate = inseminationDate;
        this.expectedCalvingDate = inseminationDate.plusDays(283);
        this.isAvailableForBreeding = false;
    }
    
    public void markCalved(LocalDate calvingDate) {
        this.pregnancyStatus = PregnancyStatus.CALVED;
        this.actualCalvingDate = calvingDate;
        // Keep unavailable until recovery period passes
    }
}
```

**File:** `src/main/java/com/livestock/management/entity/AttributeDefinition.java`
```java
@Entity
@Table(name = "attribute_definition",
       uniqueConstraints = @UniqueConstraint(
           columnNames = {"livestock_type_id", "attribute_key"}
       ))
public class AttributeDefinition {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "livestock_type_id")
    private LivestockType livestockType;
    
    @Column(nullable = false)
    private String attributeKey;
    
    @Column(nullable = false)
    private String attributeName;
    
    @Enumerated(EnumType.STRING)
    private DataType dataType;
    
    private String unit;
    private Boolean isSearchable = true;
    private Boolean isRequired = false;
    private Boolean isActive = true;
    
    @Type(JsonBinaryType.class)
    @Column(columnDefinition = "jsonb")
    private List<String> enumValues;
    
    @Type(JsonBinaryType.class)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> validationRules;
    
    private Integer displayOrder = 0;
    
    // Validation method
    public ValidationResult validate(Object value) {
        if (value == null) {
            return isRequired ? 
                ValidationResult.error("Required field") : 
                ValidationResult.ok();
        }
        
        switch (dataType) {
            case DECIMAL:
            case NUMBER:
                return validateNumeric(value);
            case ENUM:
                return validateEnum(value);
            case DATE:
                return validateDate(value);
            default:
                return ValidationResult.ok();
        }
    }
    
    private ValidationResult validateNumeric(Object value) {
        double numValue = ((Number) value).doubleValue();
        
        if (validationRules != null) {
            if (validationRules.containsKey("min") && 
                numValue < (double) validationRules.get("min")) {
                return ValidationResult.error("Value below minimum");
            }
            if (validationRules.containsKey("max") && 
                numValue > (double) validationRules.get("max")) {
                return ValidationResult.error("Value above maximum");
            }
        }
        
        return ValidationResult.ok();
    }
    
    private ValidationResult validateEnum(Object value) {
        if (enumValues != null && !enumValues.contains(value.toString())) {
            return ValidationResult.error("Invalid enum value");
        }
        return ValidationResult.ok();
    }
}
```

### Security

**File:** `src/main/java/com/livestock/management/security/JzdContextFilter.java`
```java
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class JzdContextFilter extends OncePerRequestFilter {
    
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain filterChain)
            throws ServletException, IOException {
        
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        
        if (auth != null && auth.isAuthenticated() && 
            auth.getPrincipal() instanceof UserPrincipal) {
            UserPrincipal principal = (UserPrincipal) auth.getPrincipal();
            JzdContextHolder.setJzdId(principal.getJzdId());
            
            log.debug("Set JZD context: {} for user: {}", 
                      principal.getJzdId(), principal.getUsername());
        }
        
        try {
            filterChain.doFilter(request, response);
        } finally {
            JzdContextHolder.clear();
        }
    }
    
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path.startsWith("/api/v1/auth/") || 
               path.startsWith("/public/");
    }
}
```

**File:** `src/main/java/com/livestock/management/security/JzdContextHolder.java`
```java
public class JzdContextHolder {
    private static final ThreadLocal<Long> jzdIdHolder = new ThreadLocal<>();
    
    public static void setJzdId(Long jzdId) {
        jzdIdHolder.set(jzdId);
    }
    
    public static Long getJzdId() {
        return jzdIdHolder.get();
    }
    
    public static void clear() {
        jzdIdHolder.remove();
    }
}
```

### Service Layer

**File:** `src/main/java/com/livestock/management/service/LivestockService.java`
```java
@Service
@Transactional
public class LivestockService {
    
    @Autowired
    private LivestockRepository livestockRepository;
    
    @Autowired
    private AttributeDefinitionRepository attributeRepository;
    
    @Autowired
    private ElasticsearchService elasticsearchService;
    
    public Livestock create(LivestockDto dto) {
        // Validate attributes against definitions
        List<AttributeDefinition> definitions = 
            attributeRepository.findByLivestockTypeId(dto.getLivestockTypeId());
        
        ValidationResult validation = validateAttributes(
            dto.getAttributes(), 
            definitions
        );
        
        if (!validation.isValid()) {
            throw new ValidationException(validation.getErrors());
        }
        
        // Create entity
        Livestock livestock = new Livestock();
        livestock.setJzd(getCurrentJzd());
        livestock.setFarm(getFarm(dto.getFarmId()));
        livestock.setLivestockType(getLivestockType(dto.getLivestockTypeId()));
        livestock.setRegistrationNumber(dto.getRegistrationNumber());
        livestock.setName(dto.getName());
        livestock.setSex(dto.getSex());
        livestock.setStatus(LivestockStatus.ACTIVE);
        livestock.setAttributes(dto.getAttributes());
        livestock.setIsAvailableForBreeding(
            livestock.getSex() == Sex.FEMALE && livestock.isEligibleForBreeding()
        );
        
        // Save
        Livestock saved = livestockRepository.save(livestock);
        
        // Async: Index in Elasticsearch
        elasticsearchService.indexAsync(saved);
        
        return saved;
    }
    
    public Livestock update(Long id, LivestockDto dto) {
        Livestock livestock = livestockRepository
            .findByIdAndJzdId(id, JzdContextHolder.getJzdId())
            .orElseThrow(() -> new NotFoundException("Livestock not found"));
        
        // Validate attributes
        List<AttributeDefinition> definitions = 
            attributeRepository.findByLivestockTypeId(livestock.getLivestockType().getId());
        
        ValidationResult validation = validateAttributes(
            dto.getAttributes(), 
            definitions
        );
        
        if (!validation.isValid()) {
            throw new ValidationException(validation.getErrors());
        }
        
        // Update fields
        if (dto.getName() != null) livestock.setName(dto.getName());
        if (dto.getStatus() != null) livestock.setStatus(dto.getStatus());
        if (dto.getAttributes() != null) livestock.setAttributes(dto.getAttributes());
        
        // Recalculate availability
        if (livestock.getSex() == Sex.FEMALE) {
            livestock.setIsAvailableForBreeding(livestock.isEligibleForBreeding());
        }
        
        Livestock updated = livestockRepository.save(livestock);
        
        // Re-index
        elasticsearchService.indexAsync(updated);
        
        return updated;
    }
    
    private ValidationResult validateAttributes(
            Map<String, Object> attributes,
            List<AttributeDefinition> definitions) {
        
        ValidationResult result = new ValidationResult();
        
        for (AttributeDefinition def : definitions) {
            Object value = attributes.get(def.getAttributeKey());
            ValidationResult attrResult = def.validate(value);
            
            if (!attrResult.isValid()) {
                result.addError(def.getAttributeName(), attrResult.getError());
            }
        }
        
        return result;
    }
}
```

**File:** `src/main/java/com/livestock/management/service/BreedingMatchService.java`
```java
@Service
@Transactional(readOnly = true)
public class BreedingMatchService {
    
    @Autowired
    private LivestockRepository livestockRepository;
    
    @Autowired
    private BreedingMatchRecommendationRepository matchRepository;
    
    /**
     * Finds optimal cow+bull pairings based on desired offspring attributes.
     * 
     * Algorithm:
     * 1. Query available cows and bulls within search radius
     * 2. For each possible pairing, predict offspring attributes
     * 3. Score each pairing against desired attributes
     * 4. Return top N matches sorted by score
     */
    public Page<BreedingMatchResult> findOptimalPairings(
            BreedingMatchCriteria criteria, 
            Pageable pageable) {
        
        // Step 1: Get available cows
        List<Livestock> availableCows = livestockRepository.findAvailableCows(
            criteria.getLocation().getLatitude(),
            criteria.getLocation().getLongitude(),
            criteria.getLocation().getRadiusKm()
        );
        
        // Step 2: Get available bulls
        List<Livestock> availableBulls = livestockRepository.findAvailableBulls(
            criteria.getLocation().getLatitude(),
            criteria.getLocation().getLongitude(),
            criteria.getLocation().getRadiusKm()
        );
        
        // Step 3: Generate and score all possible pairings
        List<BreedingMatchResult> allMatches = new ArrayList<>();
        
        for (Livestock cow : availableCows) {
            for (Livestock bull : availableBulls) {
                // Skip if inbreeding check enabled and animals are related
                if (criteria.isAvoidInbreeding() && areRelated(cow, bull)) {
                    continue;
                }
                
                // Predict offspring attributes
                OffspringPrediction prediction = predictOffspring(cow, bull);
                
                // Score the pairing
                MatchScore score = scorePairing(cow, bull, prediction, criteria);
                
                if (score.getTotalScore() >= 50.0) { // Minimum threshold
                    allMatches.add(new BreedingMatchResult(
                        cow, bull, prediction, score
                    ));
                }
            }
        }
        
        // Step 4: Sort by score and paginate
        allMatches.sort((a, b) -> 
            Double.compare(b.getScore().getTotalScore(), 
                          a.getScore().getTotalScore())
        );
        
        int start = (int) pageable.getOffset();
        int end = Math.min(start + pageable.getPageSize(), allMatches.size());
        List<BreedingMatchResult> pageContent = allMatches.subList(start, end);
        
        return new PageImpl<>(pageContent, pageable, allMatches.size());
    }
    
    /**
     * Predicts offspring attributes based on parent genetics.
     * Simple Mendelian model for MVP - can be enhanced with ML later.
     */
    private OffspringPrediction predictOffspring(Livestock mother, Livestock father) {
        Map<String, Object> predicted = new HashMap<>();
        
        Map<String, Object> motherAttrs = mother.getAttributes();
        Map<String, Object> fatherAttrs = father.getAttributes();
        
        // Breed prediction (simple majority or crossbred)
        String motherBreed = (String) motherAttrs.get("breed");
        String fatherBreed = (String) fatherAttrs.get("breed");
        if (motherBreed.equals(fatherBreed)) {
            predicted.put("breed", motherBreed);
        } else {
            predicted.put("breed", motherBreed + "-" + fatherBreed + " Cross");
        }
        
        // Numeric traits: average with small random variation
        predictNumericTrait(predicted, motherAttrs, fatherAttrs, "weight");
        predictNumericTrait(predicted, motherAttrs, fatherAttrs, "height");
        predictNumericTrait(predicted, motherAttrs, fatherAttrs, "leg_length");
        predictNumericTrait(predicted, motherAttrs, fatherAttrs, "milk_production");
        
        // Genetic markers (Mendelian inheritance)
        predictGeneticMarkers(predicted, motherAttrs, fatherAttrs);
        
        return new OffspringPrediction(predicted);
    }
    
    private void predictNumericTrait(Map<String, Object> predicted,
                                     Map<String, Object> motherAttrs,
                                     Map<String, Object> fatherAttrs,
                                     String traitKey) {
        Object motherValue = motherAttrs.get(traitKey);
        Object fatherValue = fatherAttrs.get(traitKey);
        
        if (motherValue instanceof Number && fatherValue instanceof Number) {
            double mother = ((Number) motherValue).doubleValue();
            double father = ((Number) fatherValue).doubleValue();
            double average = (mother + father) / 2.0;
            
            // Add small variation (±5%)
            double variation = average * 0.05;
            
            predicted.put(traitKey, average);
            predicted.put(traitKey + "_range", 
                Map.of("min", average - variation, 
                       "max", average + variation));
        }
    }
    
    private void predictGeneticMarkers(Map<String, Object> predicted,
                                      Map<String, Object> motherAttrs,
                                      Map<String, Object> fatherAttrs) {
        String motherMarkers = (String) motherAttrs.get("genetic_markers");
        String fatherMarkers = (String) fatherAttrs.get("genetic_markers");
        
        if (motherMarkers != null && fatherMarkers != null) {
            // Simple example: A2A2 dominant inheritance
            if (motherMarkers.contains("A2A2") && fatherMarkers.contains("A2A2")) {
                predicted.put("genetic_markers", "A2A2 Beta-casein (100% probability)");
            } else if (motherMarkers.contains("A2") && fatherMarkers.contains("A2")) {
                predicted.put("genetic_markers", "A2A2 Beta-casein (50% probability)");
            }
            // Can be extended with more sophisticated genetics
        }
    }
    
    /**
     * Scores a cow+bull pairing against desired offspring criteria.
     */
    private MatchScore scorePairing(Livestock cow, 
                                    Livestock bull,
                                    OffspringPrediction prediction,
                                    BreedingMatchCriteria criteria) {
        
        MatchScore score = new MatchScore();
        
        // 1. Breed compatibility (30% weight)
        score.setBreedCompatibility(
            calculateBreedCompatibility(prediction, criteria)
        );
        
        // 2. Attribute match (40% weight)
        score.setAttributeMatch(
            calculateAttributeMatch(prediction, criteria.getDesiredAttributes())
        );
        
        // 3. Genetic diversity (20% weight)
        score.setGeneticDiversity(
            calculateGeneticDiversity(cow, bull)
        );
        
        // 4. Location feasibility (10% weight)
        score.setLocationFeasibility(
            calculateLocationFeasibility(cow, bull, criteria)
        );
        
        // Calculate weighted total
        double total = (score.getBreedCompatibility() * 0.3) +
                      (score.getAttributeMatch() * 0.4) +
                      (score.getGeneticDiversity() * 0.2) +
                      (score.getLocationFeasibility() * 0.1);
        
        score.setTotalScore(total);
        
        return score;
    }
    
    private double calculateAttributeMatch(OffspringPrediction prediction,
                                           Map<String, Object> desired) {
        int totalAttributes = desired.size();
        int matchedAttributes = 0;
        
        for (Map.Entry<String, Object> entry : desired.entrySet()) {
            String key = entry.getKey();
            Object desiredValue = entry.getValue();
            Object predictedValue = prediction.getAttributes().get(key);
            
            if (predictedValue == null) continue;
            
            // Range check for numeric attributes
            if (desiredValue instanceof Map) {
                Map<String, Object> range = (Map<String, Object>) desiredValue;
                if (range.containsKey("min") && range.containsKey("max")) {
                    double predicted = ((Number) predictedValue).doubleValue();
                    double min = ((Number) range.get("min")).doubleValue();
                    double max = ((Number) range.get("max")).doubleValue();
                    
                    if (predicted >= min && predicted <= max) {
                        matchedAttributes++;
                    }
                }
            } else if (desiredValue.equals(predictedValue)) {
                matchedAttributes++;
            }
        }
        
        return totalAttributes > 0 ? 
            (matchedAttributes * 100.0 / totalAttributes) : 100.0;
    }
    
    private double calculateGeneticDiversity(Livestock cow, Livestock bull) {
        // Simple heuristic: different breeds = higher diversity
        String cowBreed = (String) cow.getAttributes().get("breed");
        String bullBreed = (String) bull.getAttributes().get("breed");
        
        if (!cowBreed.equals(bullBreed)) {
            return 95.0; // High diversity for crossbreeding
        } else {
            return 70.0; // Lower for same breed (still acceptable)
        }
        
        // Future: Calculate inbreeding coefficient from pedigree
    }
    
    private double calculateLocationFeasibility(Livestock cow, 
                                                Livestock bull,
                                                BreedingMatchCriteria criteria) {
        double cowDistance = calculateDistance(
            criteria.getLocation().getLatitude(),
            criteria.getLocation().getLongitude(),
            cow.getFarm().getLatitude(),
            cow.getFarm().getLongitude()
        );
        
        double bullDistance = calculateDistance(
            criteria.getLocation().getLatitude(),
            criteria.getLocation().getLongitude(),
            bull.getFarm().getLatitude(),
            bull.getFarm().getLongitude()
        );
        
        double maxDistance = criteria.getLocation().getRadiusKm();
        double avgDistance = (cowDistance + bullDistance) / 2.0;
        
        // Score decreases as average distance increases
        return Math.max(0, 100.0 - (avgDistance / maxDistance * 50.0));
    }
    
    private boolean areRelated(Livestock cow, Livestock bull) {
        // Simple check: same parent IDs in attributes
        Object cowMotherId = cow.getAttributes().get("mother_id");
        Object cowFatherId = cow.getAttributes().get("father_id");
        Object bullMotherId = bull.getAttributes().get("mother_id");
        Object bullFatherId = bull.getAttributes().get("father_id");
        
        if (cowMotherId != null && bullMotherId != null && 
            cowMotherId.equals(bullMotherId)) {
            return true; // Same mother
        }
        
        if (cowFatherId != null && bullFatherId != null && 
            cowFatherId.equals(bullFatherId)) {
            return true; // Same father
        }
        
        return false;
        
        // Future: Implement proper pedigree analysis with inbreeding coefficient
    }
    
    @Transactional
    public void saveRecommendation(BreedingMatchResult match, Long userId) {
        BreedingMatchRecommendation record = new BreedingMatchRecommendation();
        record.setRequestedBy(userId);
        record.setCow(match.getCow());
        record.setBull(match.getBull());
        record.setMatchScore(match.getScore().getTotalScore());
        record.setPredictedOffspring(match.getPrediction().getAttributes());
        record.setMatchReasoning(match.getScore().toJson());
        
        matchRepository.save(record);
    }
}
```

---

## 14. Verification Plan

### End-to-End Testing Scenarios

**1. Livestock Registration Flow**
- Admin logs in
- Creates new farm
- Registers cow with all attributes
- Uploads 3 photos, sets one as primary
- Verifies livestock appears in search
- Success: Livestock detail page shows all data correctly

**2. Breeding Search Flow (Direct Search)**
- Sperm collector logs in
- Searches for bulls: breed=Holstein, weight 800-1000kg, within 50km of Prague
- Views search results in grid view
- Switches to map view, verifies locations
- Clicks bull detail, views photos and attributes
- **Also searches for cows** with sex=FEMALE filter
- Success: All filters work, results accurate, bidirectional search functional

**2b. Outcome-Based Breeding Match Flow**
- Inseminator logs in
- Navigates to "Breeding Match Planner" tab
- Specifies desired calf attributes:
  - Breed: Holstein
  - Target weight: 700-800 kg
  - Target height: 155-165 cm
  - Genetic markers: A2A2 Beta-casein
  - Milk production: min 30 liters/day
- Sets location: Prague, 100km radius
- Enables "Avoid inbreeding" option
- Clicks "Find Matches"
- Views top 10 cow+bull pairings with predictions
- Reviews match #1: 95.5% score, sees predicted offspring attributes
- Clicks "View Cow Details" to inspect mother
- Clicks "View Bull Details" to inspect father
- Clicks "Schedule Insemination" directly from pairing card
- Success: Optimal pairings found, predictions accurate, seamless scheduling

**3. Insemination Appointment Flow**
- Inseminator logs in
- Searches for available cows
- Selects cow, clicks "Schedule Insemination"
- Creates appointment for next week
- Records insemination on appointment date
- Success: Appointment created, insemination record pending

**4. Pregnancy Confirmation Flow**
- Veterinarian logs in
- Views "Pending confirmations" on dashboard
- Opens insemination record
- Confirms pregnancy
- Verifies cow marked as pregnant, expected calving date calculated
- Success: Cow unavailable for breeding, farm owner notified

**5. Import/Export Flow**
- Admin prepares CSV with 100 livestock records
- Imports via batch import endpoint
- Verifies 100 records created successfully
- Exports all livestock as Excel
- Compares exported data with original
- Success: All data imported and exported correctly

**6. Attribute Definition Update**
- Admin imports new attribute definitions from CSV
- Previews changes
- Applies changes
- Registers new livestock, sees new attributes in form
- Success: Dynamic forms updated without code changes

### API Testing

**Postman collection with tests for:**
- Authentication (login, refresh, logout)
- Livestock CRUD
- Advanced search (all filter combinations)
- Appointments CRUD
- Insemination record creation and confirmation
- Health records
- Import/export endpoints
- Attribute management

### Load Testing

**JMeter script:**
- 10,000 virtual users
- Mixed workload (search, view, create, update)
- Verify: All responses < 1s, error rate < 0.5%

### Database Testing

- Verify all foreign keys enforced
- Verify JZD isolation (cross-tenant queries blocked)
- Verify JSONB queries performance
- Verify GIN index effectiveness

### Security Testing

- Penetration testing (OWASP Top 10)
- SQL injection attempts
- XSS attempts
- CSRF protection
- JWT token expiry and refresh
- Role-based access control enforcement

---

## 15. Implementation Roadmap (30 weeks)

### Phase 1: Foundation (Weeks 1-4)
- Project setup (Maven, Spring Boot 3.2, PostgreSQL)
- Database schema (Flyway migrations)
- JWT authentication
- Multi-tenancy context filter
- Basic user/JZD/farm CRUD
- **Deliverable:** Login works, users can create farms

### Phase 2: Core Livestock Management (Weeks 5-8)
- Livestock entity with JSONB attributes
- Attribute definition system
- Dynamic form generation (frontend)
- Livestock CRUD API
- Photo upload to S3/MinIO
- Thumbnail generation
- **Deliverable:** Can register livestock with photos

### Phase 3: Search & Browse (Weeks 9-12)
- Elasticsearch integration
- Advanced search API (bidirectional: cows AND bulls)
- Search UI with filters
- Grid/List/Map views
- Location-based search (PostGIS)
- Saved searches
- **NEW:** Breeding Match Planner
  - Outcome-based search API endpoint
  - Genetic prediction algorithm (BreedingMatchService)
  - Offspring attribute prediction logic
  - Match scoring system
  - Breeding Match Planner UI (Tab 2 on search page)
  - Pairing result cards with predictions
- **Deliverable:** Comprehensive search works including outcome-based breeding matches

### Phase 4: Appointments (Weeks 13-15)
- Appointment entity and API
- Calendar UI
- Create/confirm/complete/cancel appointments
- Email notifications
- **Deliverable:** Appointment system functional

### Phase 5: Insemination & Pregnancy (Weeks 16-18)
- Insemination record entity
- Record insemination API
- Pregnancy confirmation workflow
- Scheduled jobs (daily status updates)
- Calving record
- **Deliverable:** Full pregnancy tracking works

### Phase 6: Health Records (Weeks 19-20)
- Health record entity and API
- Veterinarian workflows
- Health history UI
- **Deliverable:** Vets can record health events

### Phase 7: Import/Export (Weeks 21-22)
- Batch livestock import (CSV, Excel)
- Batch export
- Attribute definition import with preview
- Validation and error reporting
- **Deliverable:** Bulk operations work

### Phase 8: Performance Optimization (Weeks 23-25)
- Query optimization
- Redis caching implementation
- Elasticsearch tuning
- Load testing with JMeter
- Kubernetes deployment
- Database read replicas
- **Deliverable:** System handles 10k concurrent users

### Phase 9: Testing & QA (Weeks 26-28)
- Unit tests (80% coverage)
- Integration tests
- E2E tests (Selenium)
- Security testing
- UAT with real users
- Bug fixes
- **Deliverable:** Production-ready quality

### Phase 10: Deployment & Launch (Weeks 29-30)
- CI/CD pipeline (Jenkins/GitLab CI)
- Production infrastructure (Kubernetes, monitoring)
- Data migration (if replacing legacy system)
- Documentation (API docs, user manual)
- Training for JZD admins
- Launch
- **Deliverable:** System live in production

---

## Summary

This specification provides a complete blueprint for building a regional livestock management platform serving 100k users across multiple agricultural cooperatives in the Czech Republic.

**Key Design Highlights:**
- **Flexible Attribute System:** JSONB-based attributes allow easy customization via CSV/JSON import
- **Multi-Tenancy:** Shared database with JZD isolation for regional collaboration
- **Scalability:** Elasticsearch, Redis caching, read replicas, Kubernetes for 100k users
- **Pregnancy Tracking:** Complete workflow from insemination to calving with automated status updates
- **Simple UI:** Bootstrap 5 + Thymeleaf for clean, readable interface
- **REST API:** Comprehensive API for import/export and third-party integration
- **Bidirectional Search:** Search for cows OR bulls based on any criteria
- **Outcome-Based Breeding:** Find optimal cow+bull pairings to achieve desired calf attributes with genetic predictions

**Next Steps:**
1. Review and approve this specification
2. Set up development environment (Spring Boot, PostgreSQL, Redis, Elasticsearch)
3. Initialize Git repository
4. Begin Phase 1 implementation (Foundation)
5. Iterate with stakeholder feedback

The 30-week roadmap provides a realistic timeline for delivering a production-ready system with proper testing and performance optimization.