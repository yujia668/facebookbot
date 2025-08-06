import os
import pandas as pd

# Paths
input_txt    = 'text.txt'
output_csv   = 'accounts_login.csv'

# The raw header your TXT should have (in this exact order)
raw_headers = ['UID','Password','2FA','Email','Cookie','Token']

# The final schema/order you want
final_headers = ['email','password','cookies','2fa','token','uid']

# 1. Make sure the input file exists; if not, create it with the raw header
if not os.path.exists(input_txt):
    with open(input_txt, 'w', encoding='utf-8') as f:
        f.write('|'.join(raw_headers) + '\n')

# 2. Try reading with header=0
df = pd.read_csv(
    input_txt,
    sep=r'\|',
    engine='python',
    dtype=str,
    skipinitialspace=True
)

# 3. Detect if the raw headers are actually present
if not set(raw_headers).issubset(df.columns):
    # No header present: re-read as header-less and assign raw_headers
    df = pd.read_csv(
        input_txt,
        sep=r'\|',
        engine='python',
        header=None,
        dtype=str,
        skipinitialspace=True
    )
    df.columns = raw_headers

# 4. Rename to match your target schema
df = df.rename(columns={
    'Email':    'email',
    'Password': 'password',
    'Cookie':   'cookies',
    '2FA':      '2fa',
    'Token':    'token',
    'UID':      'uid'
})

# 5. Reorder columns into the exact sequence you want
df = df[final_headers]

# 6. Save out to account_login.csv (will overwrite or create anew)
df.to_csv(output_csv, index=False, encoding='utf-8')

print(f"→ '{output_csv}' written with columns: {df.columns.tolist()}")
