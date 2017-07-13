AMI_LAUNCH_INDEX=$(curl -s http://169.254.169.254/latest/meta-data/ami-launch-index)
MASTER_ID=$(expr $AMI_LAUNCH_INDEX + 1) # AMI_LAUNCH_INDEX is 0 indexed, master cannot be set to 0.

# Start master service
. /root/.bashrc && nohup treadmill admin install --profile aws master --master-id ${MASTER_ID}  --run > master_services.out 2>&1 &
