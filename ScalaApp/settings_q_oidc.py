
# Quadrivium OpenID Connect settings
OIDC_RP_CLIENT_ID = 'scaladining'
OIDC_RP_CLIENT_SECRET = '707e5260-39b9-4bd9-9d4d-da5ec5081fd1'
OIDC_OP_AUTHORIZATION_ENDPOINT = "https://keycloak.esmgquadrivium.nl/auth/realms/esmgquadrivium/protocol/openid-connect/auth"
OIDC_OP_TOKEN_ENDPOINT = "https://keycloak.esmgquadrivium.nl/auth/realms/esmgquadrivium/protocol/openid-connect/token"
OIDC_OP_USER_ENDPOINT = "https://keycloak.esmgquadrivium.nl/auth/realms/esmgquadrivium/protocol/openid-connect/userinfo"
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_OP_JWKS_ENDPOINT = "https://keycloak.esmgquadrivium.nl/auth/realms/esmgquadrivium/protocol/openid-connect/certs"

# Association that will be used for automatic membership creation. If empty, no membership will be created.
OIDC_ASSOCIATION_SLUG = "esmgq"
