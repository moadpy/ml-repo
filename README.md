# Machine Learning Repository (`ml-repo`)

Ce dépôt représente le "cerveau" de la plateforme RAG.
Il ne contient **aucun code applicatif**, uniquement la base de connaissances et la configuration IA.

## Structure
- `prompts/` : Fichiers `.txt` contenant les System Prompts.
- `procedures/` : Fichiers `.md` d'aide à la résolution d'incidents CloudWatch/EC2/RDS.
- `.github/workflows/s3_sync.yml` : Pipeline livrant automatiquement ces documents dans le S3 Sandbox.
