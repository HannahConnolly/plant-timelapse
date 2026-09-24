# Plant Timelapse & Environmental Monitor

A Raspberry Pi plant-monitoring system. It reads a DHT11 temperature/humidity sensor every hour, takes a daily webcam photo, stores everything in SQLite, and serves a local web dashboard. Reports go to Discord: hourly sensor readings, a daily photo with climate averages, a daily Google Gemini plant-health assessment, and a weekly growth GIF.

## Features

- **Sensor readings**: DHT11 temperature and humidity on GPIO 4, with retries for the sensor's frequent timing errors.
- **VPD**: Vapor Pressure Deficit in kPa, calculated from the Tetens equation.
- **Daily photo**: A webcam capture saved as `data/photos/MM-DD-YYYY.jpg`.
- **History**: SQLite tables for readings and photos, plus a view of daily averages.
- **Dashboard**: A Flask page showing the latest photo and reading, and a JSON history API. It runs as a systemd service that starts on boot.
- **Discord reports**: Each report type can post to its own webhook.
  - Hourly: temperature, humidity and VPD.
  - Daily: the photo plus the day's average climate.
  - Daily: a Gemini 2.5 Flash assessment covering visual health, climate analysis and recommendations.
  - Weekly: a looping growth GIF built from every daily photo, with each frame labelled by date.
- **S3 backup** (optional): Each daily photo and weekly GIF is copied to an AWS S3 bucket.
- **AWS IoT Core** (optional): Each hourly reading is published over MQTT, and an IoT Rule stores it in DynamoDB.
- **AWS Lambda** (optional): When a daily photo lands in S3, a Lambda function asks Gemini for a health report and posts it to Discord.
- **Tests**: The suite runs on machines without the Raspberry Pi hardware libraries.

## Hardware

- Raspberry Pi running Raspberry Pi OS
- DHT11 temperature and humidity sensor
- USB webcam (opened as video device 0)
- Jumper wires

### DHT11 wiring

| DHT11 pin | Raspberry Pi |
| --- | --- |
| VCC | 3.3V (physical pin 1) or 5V (physical pin 2) |
| DATA | GPIO 4 (physical pin 7) |
| GND | Ground (physical pin 6) |

## Setup

From the project root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then fill in `.env`. Never commit it; it is already in `.gitignore`.

| Variable | Used by | Notes |
| --- | --- | --- |
| `DISCORD_SENSOR_WEBHOOK_URL` | Hourly reading | Required for the default command |
| `DISCORD_PHOTO_WEBHOOK_URL` | Daily photo | Required for `--photo` |
| `DISCORD_GEMINI_WEBHOOK_URL` | Gemini assessment | Required for `--ai` |
| `GEMINI_API_KEY` | Gemini assessment | Required for `--ai` |
| `DISCORD_ANIMATION_WEBHOOK_URL` | Growth GIF | Optional; falls back to `DISCORD_PHOTO_WEBHOOK_URL` |

The `data/` directory, the SQLite database (`data/plant_monitor.db`), and the photo and animation folders are created automatically as needed. `data/` is git-ignored.

## Commands

`src/main.py` is the command-line entry point. Run it from the project root, because the camera and Gemini code use paths relative to it.

| Command | What it does |
| --- | --- |
| `python -m src.main` | Reads the DHT11, stores the reading, and posts it to the sensor webhook |
| `python -m src.main --photo` | Captures a webcam photo and posts it with today's climate averages |
| `python -m src.main --ai` | Sends the latest photo and today's averages to Gemini and posts the structured assessment |
| `python -m src.main --animation` | Builds a GIF from every daily photo (at least 2 are needed), saves it to `data/animations/`, and posts it |

The hardware modules can also be run on their own for a quick check:

```bash
python src/sensors/dht11.py    # prints a single reading as a table
python src/sensors/camera.py   # captures and saves one photo
```

## Scheduling with cron

The reports are run by the user's crontab (`crontab -e`). The current schedule:

```cron
# Hourly sensor reading
00 * * * * cd /home/hannah/plant-timelapse && /home/hannah/plant-timelapse/venv/bin/python src/main.py >> /home/hannah/plant-timelapse.log 2>&1
# Daily photo at 22:05
05 22 * * * cd /home/hannah/plant-timelapse && /home/hannah/plant-timelapse/venv/bin/python src/main.py --photo >> /home/hannah/plant-timelapse.log 2>&1
# Weekly growth GIF, Saturdays at 22:15
15 22 * * 6 cd /home/hannah/plant-timelapse && /home/hannah/plant-timelapse/venv/bin/python src/main.py --animation >> /home/hannah/plant-timelapse.log 2>&1
```

All output is appended to `~/plant-timelapse.log`.

The nightly Gemini assessment is no longer a cron job. The AWS Lambda function runs it when the 22:05 photo reaches S3 (see [AWS Lambda Gemini report](#aws-lambda-gemini-report)). If you don't use the Lambda, add `--ai` back at 22:10:

```bash
10 22 * * * cd /home/hannah/plant-timelapse && /home/hannah/plant-timelapse/venv/bin/python src/main.py --ai >> /home/hannah/plant-timelapse.log 2>&1
```

## Dashboard

The Flask dashboard runs on port 5000. Open `http://<raspberry-pi-ip>:5000/` to see the latest photo, temperature (°F), humidity and VPD.

| Route | Returns |
| --- | --- |
| `GET /` | Dashboard page |
| `GET /api/history` | The latest 24 readings as JSON |
| `GET /photos/<filename>` | A captured image from `data/photos/` |

To run it by hand for development:

```bash
python -m src.app
```

### Start the dashboard on boot

A systemd unit is included at `deploy/plant-dashboard.service`. It runs the dashboard as `hannah` from the project root, starts once the network is up, and restarts it 5 seconds after a crash. To install it:

```bash
sudo cp deploy/plant-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now plant-dashboard.service
```

Useful commands:

```bash
systemctl status plant-dashboard        # is it running?
journalctl -u plant-dashboard -f        # follow its logs
sudo systemctl restart plant-dashboard  # pick up code changes
```

After you edit the unit file, copy it again, run `daemon-reload`, and restart the service.

## Database

`DatabaseManager` (`src/database/db.py`) creates three SQLite objects:

- `readings`: timestamp, temperature in °C and °F, humidity, and VPD in kPa.
- `photos`: timestamp and file path of each captured image.
- `daily_timelapse_summary`: a view with each day's average temperature, humidity and VPD, joined to that day's photo path.

Timestamps use SQLite's `CURRENT_TIMESTAMP`, which is UTC. The daily view groups readings by UTC date.

## Gemini assessment

`--ai` sends Gemini 2.5 Flash three things: a botanist-style prompt, the most recently modified image in `data/photos/`, and the latest row of `daily_timelapse_summary`. The response is requested as JSON that matches this schema:

- `visual_assessment`: `overall_health`, `leaf_posture`, `signs_of_stress`
- `climate_analysis`: `temperature`, `vpd`
- `recommendations`: a list of 2 or 3 short actions

The result is posted to Discord as an embed titled "Automated Plant Health Assessment".

## AWS S3 backup

When `AWS_S3_BUCKET` is set in `.env`, `--photo` uploads each capture to `s3://<bucket>/photos/` and `--animation` uploads each GIF to `s3://<bucket>/animations/`. If an upload fails, the error is logged and the Discord report still goes out. If the variable is not set, nothing is uploaded.

### One-time setup

1. **Create an AWS account** at <https://aws.amazon.com>. Then, signed in as the root user:
   - Turn on MFA for the root user (account menu → **Security credentials**).
   - Create a budget alert (**Billing and Cost Management → Budgets → Create budget → Zero spend budget** or a monthly budget of about $5).

   After this, use the root user only for account settings.

2. **Create the bucket.** In the S3 console, choose **Create bucket**:
   - Name: must be unique across all of AWS, e.g. `plant-timelapse-<yourname>`.
   - Region: one near you, e.g. `us-east-2` (Ohio). Use the same region for everything else, including the IoT Core setup below.
   - Bucket namespace: **Global namespace**, so the bucket keeps exactly the name you typed.
   - Leave the other defaults: **ACLs disabled**, **Block all public access** on, versioning off, and SSE-S3 encryption.

3. **Create an IAM user for the Pi.** In the IAM console, go to **Users → Create user**, name it `plant-pi`, and leave console access off. Skip the permissions step. Open the new user, then **Add permissions → Create inline policy → JSON**, and paste this with your bucket name:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "s3:PutObject",
         "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
       },
       {
         "Effect": "Allow",
         "Action": "s3:ListBucket",
         "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME"
       }
     ]
   }
   ```

   This is least privilege: the Pi can add files to this one bucket and list them. It cannot read, delete or touch anything else in your account. Name the policy `plant-pi-s3-upload`.

4. **Create an access key.** On the user's **Security credentials** tab, choose **Create access key → Application running outside AWS**. Copy both values; the secret is shown only once.

5. **Configure the Pi.** Install the AWS CLI and store the key:

   ```bash
   sudo apt install awscli
   aws configure
   # AWS Access Key ID:     <from step 4>
   # AWS Secret Access Key: <from step 4>
   # Default region name:   <your bucket's region>
   # Default output format: json
   ```

   This writes `~/.aws/credentials` and `~/.aws/config`. boto3 reads these automatically, so the keys never go in `.env` or in the repo.

6. **Point the app at the bucket.** Add this to `.env`:

   ```dotenv
   AWS_S3_BUCKET="plant-timelapse-yourname"
   ```

### Check it works

```bash
aws sts get-caller-identity              # shows the plant-pi user, so the credentials work
python -m src.main --photo               # log should end with "Backed up ... to s3://..."
aws s3 ls s3://plant-timelapse-yourname/photos/
```

`aws s3 rm` fails with `AccessDenied`, which is expected, because the policy doesn't allow deletes. To remove a file, delete it in the S3 console while signed in as yourself.

To copy photos taken before S3 was set up:

```bash
aws s3 sync data/photos/ s3://plant-timelapse-yourname/photos/
```

## AWS IoT Core readings

When `AWS_IOT_ENDPOINT` is set in `.env`, every hourly reading is also published to AWS IoT Core. If publishing fails, the error is logged and the Discord report still goes out.

```text
Pi (hourly cron) --MQTT over TLS, port 8883--> IoT Core topic plant/plant-pi/readings
                                                   |
                                   IoT Rule: SELECT * FROM 'plant/+/readings'
                                                   |
                                          DynamoDB table plant-readings
```

The Pi signs in with an X.509 device certificate instead of access keys. Each message looks like this:

```json
{"device_id": "plant-pi", "timestamp": "2026-09-24T17:00:06Z", "temperature_c": 25.3,
 "temperature_f": 77.5, "humidity": 73.0, "vpd_kpa": 0.87}
```

### One-time setup

Do these steps in your bucket's region (`us-east-2` here). Replace `ACCOUNT_ID` with your 12-digit account number, shown in the account menu at the top right.

1. **Create the DynamoDB table.** Search the console for **DynamoDB**. It is its own service, not the **Table buckets** page inside S3. Choose **Tables → Create table**:
   - Table name: `plant-readings`
   - Partition key: `device_id` (String)
   - Sort key: `timestamp` (String)
   - Under **Table settings**, choose **Customize settings** and then **On-demand** capacity. At 24 writes a day, the cost is effectively zero.

2. **Create the IoT policy.** In IoT Core, go to **Security → Policies → Create policy**, name it `plant-pi-policy`, switch to **JSON**, and paste:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "iot:Connect",
         "Resource": "arn:aws:iot:us-east-2:ACCOUNT_ID:client/plant-pi"
       },
       {
         "Effect": "Allow",
         "Action": "iot:Publish",
         "Resource": "arn:aws:iot:us-east-2:ACCOUNT_ID:topic/plant/plant-pi/readings"
       }
     ]
   }
   ```

   The Pi may connect only as client `plant-pi` and publish only to its own readings topic.

3. **Register the Pi as a Thing.** Go to **Manage → All devices → Things → Create things → Create single thing**:
   - Thing name: `plant-pi`. Choose **No shadow**.
   - Device certificate: **Auto-generate a new certificate**.
   - Policies: tick `plant-pi-policy`, then **Create thing**.
   - Download the **device certificate**, the **private key** and **Amazon Root CA 1**. You can skip the public key and Amazon Root CA 3. The private key is shown only once, so download everything before you click **Done**.

4. **Put the certificates on the Pi.** Create a private folder for them on the Pi:

   ```bash
   mkdir -p ~/.plant-iot && chmod 700 ~/.plant-iot
   ```

   If you downloaded the files on another computer, copy them over from that computer:

   ```bash
   cd ~/Downloads
   scp *-certificate.pem.crt *-private.pem.key AmazonRootCA1.pem <user>@<pi-ip>:~/.plant-iot/
   ```

   Then delete them from that computer's Downloads folder, so the private key only exists on the Pi. If you downloaded them on the Pi itself, move them in instead:

   ```bash
   mv ~/Downloads/*-certificate.pem.crt ~/Downloads/*-private.pem.key ~/Downloads/AmazonRootCA1.pem ~/.plant-iot/
   ```

   On the Pi, give the files the names the app expects and make them readable only by you:

   ```bash
   cd ~/.plant-iot
   mv *-certificate.pem.crt certificate.pem.crt
   mv *-private.pem.key private.pem.key
   chmod 600 *
   ```

   The certificates are kept outside the project folder so they can never be committed.

5. **Create the IoT Rule.** Go to **Message routing → Rules → Create rule**:
   - Rule name: `plant_readings_to_dynamodb`. Rule names can't contain hyphens.
   - SQL statement: `SELECT * FROM 'plant/+/readings'`
   - Action: **DynamoDBv2**, table `plant-readings`. Plain **DynamoDB** would store the whole message in a single column; DynamoDBv2 gives each JSON field its own column.
   - IAM role: **Create new role**, named `plant-iot-dynamodb-role`.

   The role is what lets IoT Core write to DynamoDB for you. The Pi's certificate has no DynamoDB permissions at all.

6. **Point the app at IoT Core.** Find your account's endpoint in either of these places:
   - IoT Core → **Connect → Domain configurations**: the domain name of the `iot:Data-ATS` row. Older consoles show it as **Settings → Device data endpoint**.
   - **CloudShell** (the `>_` icon in the console): `aws iot describe-endpoint --endpoint-type iot:Data-ATS --region us-east-2`. The Pi's `plant-pi` user isn't allowed to run this command.

   The endpoint isn't a secret; the certificate is what grants access. Add it to `.env`:

   ```dotenv
   AWS_IOT_ENDPOINT="xxxxxxxxxxxxxx-ats.iot.us-east-2.amazonaws.com"
   ```

   `AWS_IOT_THING_NAME` defaults to `plant-pi` and `AWS_IOT_CERT_DIR` defaults to `~/.plant-iot`.

### Check it works

1. In IoT Core, open **MQTT test client** and subscribe to `plant/#`.
2. On the Pi, run `python -m src.main`. The log should include `Published reading to AWS IoT topic 'plant/plant-pi/readings'`, and the message appears in the test client.
3. In DynamoDB, open **Explore items → plant-readings** and click **Run** to see the stored row.

To read a single day instead of the whole table, switch from **Scan** to **Query**: set `device_id` = `plant-pi` and `timestamp` **begins with** `2026-09-24`. A Scan reads every row, while a Query uses the keys and only reads the rows you ask for, so it stays fast and cheap as the table grows.

If the connection fails, check that the endpoint is the `-ats` one, that the three files in `~/.plant-iot` have the right names, and that the certificate is **Active** and has `plant-pi-policy` attached.

## AWS Lambda Gemini report

`aws_lambda/gemini_report/lambda_function.py` moves the nightly Gemini assessment off the Pi. When a daily photo is uploaded to S3, S3 invokes the function, which:

```text
S3 photos/MM-DD-YYYY.jpg ──ObjectCreated──▶ Lambda plant-gemini-report
                                              ├─ S3: downloads the photo
                                              ├─ DynamoDB: queries the last 24 hours of readings
                                              ├─ Parameter Store: reads the Gemini key and Discord webhook
                                              ├─ Gemini 2.5 Flash: gets the structured assessment
                                              └─ Discord: posts the embed with the photo attached
```

Notes on how it behaves:
- **Single file:** it uses only the standard library and boto3, which the Lambda Python runtime includes. There's nothing to package, so you paste the file into the console.
- **Rolling 24 hours:** it averages the last 24 hours of readings, instead of the UTC calendar day used by `--ai`.
- **Skips old and undated photos:** files like `demo.jpg`, or photos more than a day old, are ignored. This way `aws s3 sync` doesn't trigger a report for every old photo.
- **Retries:** if Gemini is overloaded (429 or 5xx), it retries twice, after 5 and 15 seconds. If it still fails, the invocation fails, and S3 retries it later.

The prompt and response schema mirror `src/services/genai.py`. Keep them in sync.

### One-time setup

Use the same region as the bucket. Replace `ACCOUNT_ID` with your 12-digit account number.

1. **Store the secrets in Parameter Store.** Go to **Systems Manager → Parameter Store → Create parameter** and create two parameters, each with **Tier:** Standard, **Type:** SecureString and the default KMS key (`alias/aws/ssm`):

   | Name | Value |
   | --- | --- |
   | `/plant-timelapse/gemini-api-key` | your `GEMINI_API_KEY` |
   | `/plant-timelapse/discord-gemini-webhook` | your `DISCORD_GEMINI_WEBHOOK_URL` |

   Standard parameters are free. Secrets Manager would cost $0.40 per secret per month.

2. **Create the function.** Go to **Lambda → Create function → Author from scratch**:
   - Name: `plant-gemini-report`
   - Runtime: **Python 3.12**. Architecture: **arm64**, which is cheaper, and the code has no compiled dependencies.
   - Execution role: **Create a new role with basic Lambda permissions**. This lets the function write to CloudWatch Logs.

3. **Add the code.** On the **Code** tab, open `lambda_function.py`, replace everything with the contents of `aws_lambda/gemini_report/lambda_function.py`, and click **Deploy**.

4. **Raise the timeout.** Go to **Configuration → General configuration → Edit**. Set **Timeout** to `3 min 0 sec` and **Memory** to `256 MB`. The default 3-second timeout is far too short for a Gemini call.

5. **Grant access to the data.** Go to **Configuration → Permissions** and click the role name to open it in IAM. Choose **Add permissions → Create inline policy → JSON**, paste the policy below, and name it `plant-gemini-report-access`:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/photos/*"
       },
       {
         "Effect": "Allow",
         "Action": "dynamodb:Query",
         "Resource": "arn:aws:dynamodb:us-east-2:ACCOUNT_ID:table/plant-readings"
       },
       {
         "Effect": "Allow",
         "Action": "ssm:GetParameter",
         "Resource": "arn:aws:ssm:us-east-2:ACCOUNT_ID:parameter/plant-timelapse/*"
       }
     ]
   }
   ```

   Decrypting a SecureString that uses the AWS managed `aws/ssm` key needs no separate KMS permission.

6. **Test it by hand.** On the **Test** tab, create an event from `aws_lambda/gemini_report/test_event.json`. Change the photo key and `eventTime` if needed; the photo must be at most a day older than `eventTime`. Then click **Test**. A report with that photo should appear in Discord. The **Log output** shows the climate summary and the Gemini response. Earlier runs are under **Monitor → View CloudWatch logs**.

7. **Connect the S3 trigger.** Click **Add trigger → S3**:
   - Bucket: your bucket. Event types: **All object create events**.
   - Prefix: `photos/`. Suffix: `.jpg`.
   - Tick the recursive invocation acknowledgement. The function only reads from the bucket and never writes to it, so it can't trigger itself.

8. **Retire the Pi's `--ai` job.** Remove the 22:10 `--ai` line with `crontab -e`, or you'll get two reports each night. `python -m src.main --ai` still works if you want to run it by hand.

### Costs

At one invocation a day, this stays inside the Lambda, CloudWatch Logs and Parameter Store free tiers. Gemini usage is billed by Google, as it was before.

## Tests

From the project root:

```bash
pytest
```

The tests cover:

- **Database**: initialization, inserting and reading back readings, and photo path normalization for the file server.
- **Sensor**: VPD maths, reads and cleanup, and importing without the hardware libraries.
- **Parsing**: extracting JSON from Gemini and Discord responses.
- **Animation**: photo collection and ordering, GIF output, and skipping unreadable images.
- **IoT publishing**: message shape, ISO timestamp, topic and QoS, and failed connections returning `False` (the MQTT connection is mocked).
- **Lambda Gemini report**: skipping undated and backfilled photos, averaging DynamoDB readings, the Gemini request and response, retrying when Gemini is busy, the Discord multipart upload, and the handler (all AWS and HTTP calls are mocked).
- **S3 backup**: object key and content type, and failed uploads returning `None` (the S3 client is mocked, so no AWS account is needed).

## Project layout

```text
plant-timelapse/
├── .env.example                  # Template for environment configuration
├── README.md
├── requirements.txt              # Python dependencies
├── aws_lambda/gemini_report/
│   ├── lambda_function.py        # S3-triggered Gemini report, deployed to AWS Lambda
│   └── test_event.json           # Sample S3 event for the Lambda console's Test tab
├── deploy/
│   └── plant-dashboard.service   # systemd unit that starts the dashboard on boot
├── data/                         # Created at runtime (git-ignored)
│   ├── plant_monitor.db          # SQLite database
│   ├── photos/                   # Daily captures, MM-DD-YYYY.jpg
│   └── animations/               # Generated growth GIFs
└── src/
    ├── app.py                    # Flask dashboard and API routes
    ├── main.py                   # CLI: sensor, photo, AI, and animation workflows
    ├── database/db.py            # SQLite tables, view, and queries
    ├── sensors/
    │   ├── camera.py             # Webcam capture
    │   └── dht11.py              # DHT11 reads and VPD calculation
    ├── services/
    │   ├── animation.py          # Growth GIF builder
    │   ├── discord_bot.py        # Discord webhook reports
    │   ├── genai.py              # Gemini image and climate analysis
    │   ├── iot_publisher.py      # Optional MQTT publish of readings to AWS IoT Core
    │   └── s3_backup.py          # Optional S3 upload of photos and GIFs
    ├── static/favicon.ico
    ├── templates/index.html      # Dashboard template
    └── tests/                    # Database, sensor, and animation tests
```
