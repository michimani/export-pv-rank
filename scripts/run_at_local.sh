CLIENT_SECRET_SSM_KEY=$(cat ./stack-config.json | jq -r ".lambda.env.client_secret_ssm_key") \
VIEW_ID=$(cat ./stack-config.json | jq -r ".lambda.env.view_id") \
OUT_S3_BUCKET=$(cat ./stack-config.json | jq -r ".lambda.env.out_s3_bucket") \
OUT_JSON_KEY=$(cat ./stack-config.json | jq -r ".lambda.env.out_json_key") \
SITE_BASE_URL=$(cat ./stack-config.json | jq -r ".lambda.env.site_base_url") \
python3 lambda/src/fetch_rank.py
