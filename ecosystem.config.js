module.exports = {
  apps: [
    {
      name: 'ai-voice-backend',
      script: 'app.py',
      cwd: './bot',
      interpreter: './bot/venv/bin/python',
      env: {
        NODE_ENV: 'production',
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: './logs/backend_error.log',
      out_file: './logs/backend_out.log',
    },
    {
      name: 'ai-voice-frontend',
      script: 'npm',
      args: 'run dev', // Note: On server you might prefer 'npm run build' and then 'serve'
      cwd: './DSGROUPDASHBOARD',
      env: {
        NODE_ENV: 'production',
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: './logs/frontend_error.log',
      out_file: './logs/frontend_out.log',
    },
  ],
};
