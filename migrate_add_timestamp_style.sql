-- Add timestamp and style columns to assessment_results if they don't exist
ALTER TABLE assessment_results ADD COLUMN timestamp TEXT;
ALTER TABLE assessment_results ADD COLUMN style TEXT;
