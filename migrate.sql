-- Migration Whisperer — passage au mode multi-canal
-- À exécuter UNE FOIS sur la base PostgreSQL de prod avant le redéploiement.
--
-- Connexion : gcloud sql connect whisperer-db --user=whisperer --database=whisperer

-- 1. Créer la table des canaux
CREATE TABLE IF NOT EXISTS channels (
  code        VARCHAR(32)  PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 2. Ajouter la colonne channel_code (nullable d'abord pour migrer les données)
ALTER TABLE transcriptions ADD COLUMN IF NOT EXISTS channel_code VARCHAR(32);

-- 3. Insérer un canal par défaut pour les transcriptions existantes
--    (adapter le nom si besoin)
INSERT INTO channels (code, name) VALUES ('DEFAULT', 'Ancien contenu')
  ON CONFLICT DO NOTHING;

-- 4. Rattacher toutes les transcriptions existantes au canal DEFAULT
UPDATE transcriptions SET channel_code = 'DEFAULT' WHERE channel_code IS NULL;

-- 5. Rendre la colonne NOT NULL
ALTER TABLE transcriptions ALTER COLUMN channel_code SET NOT NULL;

-- 6. Supprimer l'ancienne colonne d'identification
ALTER TABLE transcriptions DROP COLUMN IF EXISTS device_id;
ALTER TABLE transcriptions DROP COLUMN IF EXISTS user_id;

-- 7. Supprimer l'ancienne table users si elle existe
DROP TABLE IF EXISTS users;

-- 8. Mettre à jour l'index
DROP INDEX IF EXISTS idx_transcriptions_device_created;
DROP INDEX IF EXISTS idx_transcriptions_user_created;
CREATE INDEX IF NOT EXISTS idx_transcriptions_channel_created
  ON transcriptions(channel_code, created_at);

-- Vérification rapide
SELECT 'channels' AS table_name, count(*) FROM channels
UNION ALL
SELECT 'transcriptions', count(*) FROM transcriptions;
