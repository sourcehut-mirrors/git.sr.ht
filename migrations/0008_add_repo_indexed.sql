-- +brant Up
ALTER TABLE repository
ADD COLUMN indexed boolean NOT NULL DEFAULT 'f';

-- +brant Down
ALTER TABLE repository
DROP COLUMN indexed;
