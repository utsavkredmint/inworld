module.exports = {
  apps: [
    {
      name: 'ai-voice-backend',
      script: 'app.py',
      cwd: '/Users/utsav/Downloads/backup/bot',
      interpreter: '/Users/utsav/Downloads/backup/bot/venv/bin/python',
      env: {
        NODE_ENV: 'development',
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: '/Users/utsav/Downloads/backup/logs/backend_error.log',
      out_file: '/Users/utsav/Downloads/backup/logs/backend_out.log',
    },
    {
      name: 'ai-voice-frontend',
      script: 'npm',
      args: 'run dev',
      cwd: '/Users/utsav/Downloads/backup/DSGROUPDASHBOARD',
      env: {
        NODE_ENV: 'development',
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: '/Users/utsav/Downloads/backup/logs/frontend_error.log',
      out_file: '/Users/utsav/Downloads/backup/logs/frontend_out.log',
    },
  ],
};
