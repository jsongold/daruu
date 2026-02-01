# Supabase Infrastructure

This directory contains Supabase database migrations and configuration.

## Directory Structure

```
infra/supabase/
├── README.md           # This file
└── migrations/         # SQL migration files
    ├── 001_create_tables.sql   # Core tables
    ├── 002_create_indexes.sql  # Performance indexes
    └── 003_create_rls.sql      # Row Level Security
```

 1. Create a Supabase Project                                                                                                      
                                                                                                                                    
  1. Go to https://supabase.com and create an account                                                                               
  2. Click "New Project"                                                                                                            
  3. Choose your organization, name, database password, and region                                                                  
  4. Wait for the project to be created (~2 minutes)                                                                                
                                                                                                                                    
  2. Get Your Credentials                                                                                                           
                                                                                                                                    
  From your Supabase dashboard:                                                                                                     
  1. Go to Settings → API                                                                                                           
  2. Copy these values:                                                                                                             
    - Project URL → DARU_SUPABASE_URL                                                                                               
    - anon public key → DARU_SUPABASE_ANON_KEY                                                                                      
    - service_role key → DARU_SUPABASE_SERVICE_KEY (optional, for admin ops)                                                        
                                                                                                                                    
  3. Set Environment Variables                                                                                                      
                                                                                                                                    
  Create a .env file in apps/api/:                                                                                                  
                                                                                                                                    
  # Required                                                                                                                        
  DARU_SUPABASE_URL=https://xxxxx.supabase.co                                                                                       
  DARU_SUPABASE_ANON_KEY=eyJhbGc...                                                                                                 
  DARU_OPENAI_API_KEY=sk-...                                                                                                        
                                                                                                                                    
  # Optional                                                                                                                        
  DARU_SUPABASE_SERVICE_KEY=eyJhbGc...                                                                                              
  DARU_DEBUG=true                                                                                                                   
                                                                                                                                    
  4. Run Database Migrations                                                                                                        
                                                                                                                                    
  Option A: Supabase Dashboard (Recommended)                                                                                        
  1. Go to SQL Editor in your Supabase dashboard                                                                                    
  2. Run each migration file in order:                                                                                              
                                                                                                                                    
⏺ Read 1 file (ctrl+o to expand)                                                                                                    
                                                                                                                                    
⏺ infra/supabase/migrations/                                                                                                        
  ├── 001_create_tables.sql   # Core tables (documents, jobs, fields, etc.)                                                         
  ├── 002_create_indexes.sql  # Performance indexes                                                                                 
  └── 003_create_rls.sql      # Row Level Security policies                                                                         
                                                                                                                                    
  Option B: Using the Python script                                                                                                 
  cd apps/api                                                                                                                       
                                                                                                                                    
  # List available migrations                                                                                                       
  python -m app.infrastructure.supabase.migrate --list                                                                              
                                                                                                                                    
  # Output combined SQL (copy/paste into Supabase SQL Editor)                                                                       
  python -m app.infrastructure.supabase.migrate --output combined.sql                                                               
                                                                                                                                    
  5. Create Storage Buckets                                                                                                         
                                                                                                                                    
  In Supabase dashboard, go to Storage and create these buckets:                                                                    
  ┌───────────┬─────────────────────┐                                                                                               
  │  Bucket   │     Description     │                                                                                               
  ├───────────┼─────────────────────┤                                                                                               
  │ documents │ Original PDF files  │                                                                                               
  ├───────────┼─────────────────────┤                                                                                               
  │ previews  │ Page preview images │                                                                                               
  ├───────────┼─────────────────────┤                                                                                               
  │ crops     │ OCR crop images     │                                                                                               
  ├───────────┼─────────────────────┤                                                                                               
  │ outputs   │ Filled/output PDFs  │                                                                                               
  └───────────┴─────────────────────┘                                                                                               
  For each bucket:                                                                                                                  
  1. Click "New bucket"                                                                                                             
  2. Enter the name (e.g., documents)                                                                                               
  3. Set to Public or configure RLS policies                                                                                        
                                                                                                                                    
  6. Verify Setup                                                                                                                   
                                                                                                                                    
  cd apps/api                                                                                                                       
                                                                                                                                    
  # Start the server                                                                                                                
  uvicorn app.main:app --reload                                                                                                     
                                                                                                                                    
  # Check health endpoint                                                                                                           
  curl http://localhost:8000/health                                                                                                 
                                                                                                                                    
  You should see:                                                                                                                   
  {                                                                                                                                 
    "status": "healthy",                                                                                                            
    "storage": "supabase",                                                                                                          
    "database": "supabase"                                                                                                          
  }                                                                                                                                 
                                                                                                                                    
  Quick Reference                                                                                                                   
  ┌───────────────────────────────┬──────────┬───────────────────────────────────────┐                                              
  │           Variable            │ Required │              Description              │                                              
  ├───────────────────────────────┼──────────┼───────────────────────────────────────┤                                              
  │ DARU_SUPABASE_URL             │ Yes      │ Project URL (https://xxx.supabase.co) │                                              
  ├───────────────────────────────┼──────────┼───────────────────────────────────────┤                                              
  │ DARU_SUPABASE_ANON_KEY        │ Yes      │ Anonymous/public API key              │                                              
  ├───────────────────────────────┼──────────┼───────────────────────────────────────┤                                              
  │ DARU_SUPABASE_SERVICE_KEY     │ No       │ Service role key for admin            │                                              
  ├───────────────────────────────┼──────────┼───────────────────────────────────────┤                                              
  │ DARU_STORAGE_BUCKET_DOCUMENTS │ No       │ Default: documents                    │                                              
  ├───────────────────────────────┼──────────┼───────────────────────────────────────┤                                              
  │ DARU_STORAGE_BUCKET_PREVIEWS  │ No       │ Default: previews                     │                                              
  └───────────────────────────────┴──────────┴───────────────────────────────────────┘      

## Running Migrations

### Option 1: Supabase Dashboard

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Copy and paste each migration file in order
4. Execute

### Option 2: Supabase CLI

```bash
# Install Supabase CLI
npm install -g supabase

# Link to your project
supabase link --project-ref your-project-ref

# Push migrations
supabase db push
```

### Option 3: Python Script

```bash
# From project root
cd apps/api
python -m app.infrastructure.supabase.migrate --list
python -m app.infrastructure.supabase.migrate --dry-run
python -m app.infrastructure.supabase.migrate --output combined.sql
```

### Option 4: Direct PostgreSQL

```bash
# Get connection string from Supabase dashboard
psql "postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres" \
  -f infra/supabase/migrations/001_create_tables.sql
```

## Environment Variables

Required for the application to connect to Supabase:

```bash
DARU_SUPABASE_URL=https://xxxxx.supabase.co
DARU_SUPABASE_ANON_KEY=eyJhbGc...
DARU_SUPABASE_SERVICE_KEY=eyJhbGc...  # Optional, for admin operations
```

## Tables

| Table | Description |
|-------|-------------|
| `documents` | Uploaded document metadata |
| `jobs` | Processing job records |
| `fields` | Form field data |
| `issues` | Validation issues |
| `activities` | Activity log |
| `evidence` | Field linking evidence |
| `mappings` | Field mappings |
| `extractions` | OCR extraction data |

## Storage Buckets

| Bucket | Description |
|--------|-------------|
| `documents` | Original PDF files |
| `previews` | Page preview images |
| `crops` | OCR crop images |
| `outputs` | Filled/output PDFs |
