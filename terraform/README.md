Example GitHub Actions step:

```yaml
- name: Inject secrets
  uses: hashicorp/vault-action@v2
  with:
    url: ${{ secrets.VAULT_ADDR }}
    method: approle
    roleId: ${{ secrets.VAULT_ROLE_ID }}
    secretId: ${{ secrets.VAULT_SECRET_ID }}
    secrets: |
      secret/mita/prod/app DATABASE_URL >> .env
      secret/mita/prod/app REDIS_URL >> .env
      secret/mita/prod/app SENTRY_DSN >> .env
```
