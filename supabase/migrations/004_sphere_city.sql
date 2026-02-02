-- Migration: 004_sphere_city
-- Description: Add experience_level to users and city-based matching support to matches table
-- This migration enables filtering users by experience level and matching users within the same city

-- Add experience_level column to users table for skill/experience categorization
ALTER TABLE users ADD COLUMN experience_level VARCHAR(20);

-- Add city column to matches table to support city-based matching
ALTER TABLE matches ADD COLUMN city VARCHAR(100);

-- Create index on matches.city for efficient city-based queries
CREATE INDEX idx_matches_city ON matches(city);
