-- Chunk writes from Modal timed out under load (57014, statement timeout).
--
-- PostgREST runs every request as `authenticator` (statement_timeout = 8s) and then
-- switches to the role in the JWT. The service_role key carries no timeout of its
-- own, so the 8s limit applied to each 50 to 200 row upsert, which also updates
-- the HNSW and full-text indexes. Give service_role (server-side writers only) a
-- longer limit. PostgREST applies the impersonated role's settings per request.
ALTER ROLE service_role SET statement_timeout = '60s';
NOTIFY pgrst, 'reload config';
NOTIFY pgrst, 'reload schema';

-- The Modal worker never passed documents.id, so chunks were written with
-- document_id NULL and would not cascade when a document is deleted.
-- Link existing chunks to their document row by filename (= doc_key).
UPDATE public.chunks AS c
SET    document_id = d.id
FROM   public.documents AS d
WHERE  c.document_id IS NULL
  AND  d.rag_project_id = c.rag_project_id
  AND  d.filename = c.doc_key;
