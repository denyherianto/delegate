-- V14: Free-form metadata JSON on tasks + rename standard->default workflow
ALTER TABLE tasks ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}';
UPDATE tasks SET workflow = 'default' WHERE workflow = 'standard';
