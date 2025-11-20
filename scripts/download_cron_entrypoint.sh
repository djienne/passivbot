#!/bin/bash
set -e

# Configuration
COINS="AAVE ADA AVAX BCH BNB BTC DOGE DOT ETH HBAR HYPE LINK LTC SOL SUI TON TRX UNI XLM XRP ASTER"
DAYS_BACK=3
LOG_FILE="/var/log/hyperliquid_download.log"
SCRIPT_PATH="/app/src/tools/download_hyperliquid_data.py"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Function to run the download
run_download() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting Hyperliquid data download..." | tee -a "$LOG_FILE"
    python "$SCRIPT_PATH" --coins $COINS --days-back $DAYS_BACK 2>&1 | tee -a "$LOG_FILE"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Download completed" | tee -a "$LOG_FILE"
    echo "---" | tee -a "$LOG_FILE"
}

# Run download immediately on startup
echo "$(date '+%Y-%m-%d %H:%M:%S') - Container started - Running initial download..." | tee -a "$LOG_FILE"
run_download

# Set up cron job to run every 4 hours
# Cron format: minute hour day month weekday
# 0 */4 * * * means: at minute 0 of every 4th hour
echo "Setting up cron job to run every 4 hours..."

# Create a wrapper script for cron (cron has limited environment)
cat > /app/cron_download.sh << 'EOF'
#!/bin/bash
export PATH=/usr/local/bin:/usr/bin:/bin
cd /app
python /app/src/tools/download_hyperliquid_data.py --coins AAVE ADA AVAX BCH BNB BTC DOGE DOT ETH HBAR HYPE LINK LTC SOL SUI TON TRX UNI XLM XRP --days-back 3 >> /var/log/hyperliquid_download.log 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Scheduled download completed" >> /var/log/hyperliquid_download.log
echo "---" >> /var/log/hyperliquid_download.log
EOF

chmod +x /app/cron_download.sh

# Add cron job
echo "0 */4 * * * /app/cron_download.sh" | crontab -

# Start cron in foreground
echo "$(date '+%Y-%m-%d %H:%M:%S') - Cron daemon starting. Downloads will run every 4 hours." | tee -a "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Next scheduled runs: $(date -d '+4 hours' '+%Y-%m-%d %H:00:00'), $(date -d '+8 hours' '+%Y-%m-%d %H:00:00'), $(date -d '+12 hours' '+%Y-%m-%d %H:00:00')..." | tee -a "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') - To view logs: docker logs -f <container_name> OR docker exec <container_name> tail -f /var/log/hyperliquid_download.log" | tee -a "$LOG_FILE"

# Keep container running with cron in foreground
cron && tail -f "$LOG_FILE"
