CREATE TABLE ai.grant_reviews (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    meta_data JSONB,
    embedding VECTOR(1536),
    document_type TEXT,
    usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    content_hash TEXT,
    filters JSONB DEFAULT '{}'::jsonb
);

-- Create indexes
CREATE INDEX idx_grant_reviews_embedding 
ON ai.grant_reviews USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX idx_grant_reviews_user_id 
ON ai.grant_reviews ((meta_data->>'user_id'));

CREATE INDEX idx_grant_reviews_created_at 
ON ai.grant_reviews (created_at DESC);