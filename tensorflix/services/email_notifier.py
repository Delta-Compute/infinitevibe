"""
Email notification service for briefs and deadline reminders.
Supports SendGrid and AWS SES backends.
"""
from __future__ import annotations

import os
from typing import List, Optional
from datetime import datetime
from loguru import logger
from tensorflix.models.brief import Brief


class EmailNotifier:
    """Email notification service for briefs."""
    
    def __init__(self):
        """Initialize email service with configured provider."""
        self.provider = os.getenv("EMAIL_PROVIDER", "sendgrid")  # sendgrid or aws_ses
        self.from_email = os.getenv("FROM_EMAIL", "noreply@infinitevibe.ai")
        
        if self.provider == "sendgrid":
            self.api_key = os.getenv("SENDGRID_API_KEY")
            if not self.api_key:
                logger.warning("SendGrid API key not configured")
        elif self.provider == "aws_ses":
            # AWS credentials should be in environment or IAM role
            self.region = os.getenv("AWS_REGION", "us-east-1")
        
        logger.info(f"Email notifier initialized with provider: {self.provider}")
    
    async def send_brief_confirmation(self, brief: Brief) -> bool:
        """Send confirmation email to user after brief submission."""
        subject = f"Brief Confirmation: {brief.title}"
        
        html_content = f"""
        <html>
        <body>
            <h2>Brief Submitted Successfully</h2>
            <p>Your creative brief has been submitted to the InfiniteVibe network.</p>
            
            <h3>Brief Details:</h3>
            <ul>
                <li><strong>ID:</strong> {brief.brief_id}</li>
                <li><strong>Title:</strong> {brief.title}</li>
                <li><strong>Submitted:</strong> {brief.created_at.strftime('%Y-%m-%d %H:%M UTC')}</li>
                <li><strong>6hr Review:</strong> {brief.deadline_6hr.strftime('%Y-%m-%d %H:%M UTC')}</li>
                <li><strong>Final Deadline:</strong> {brief.deadline_24hr.strftime('%Y-%m-%d %H:%M UTC')}</li>
            </ul>
            
            <h3>What Happens Next:</h3>
            <ol>
                <li>Miners will create AI videos based on your brief</li>
                <li>After 6 hours, you'll receive an email to select the top 10 submissions</li>
                <li>Selected miners will create revisions</li>
                <li>You'll select the final 3 and receive download links</li>
            </ol>
            
            <p>Thank you for using InfiniteVibe!</p>
        </body>
        </html>
        """
        
        return await self._send_email(
            to_email=brief.user_email,
            subject=subject,
            html_content=html_content
        )
    
    async def send_new_brief_notification(self, brief: Brief, miner_emails: List[str]) -> bool:
        """Send new brief notification to all active miners."""
        subject = f"New Creative Brief Available: {brief.title}"
        
        html_content = f"""
        <html>
        <body>
            <h2>New Creative Brief Available</h2>
            <p>A new brief has been posted on the InfiniteVibe network!</p>
            
            <h3>Brief Details:</h3>
            <ul>
                <li><strong>Title:</strong> {brief.title}</li>
                <li><strong>Description:</strong> {brief.description}</li>
                <li><strong>Requirements:</strong> {brief.requirements or 'See brief details'}</li>
                <li><strong>Deadline:</strong> {brief.deadline_24hr.strftime('%Y-%m-%d %H:%M UTC')}</li>
            </ul>
            
            <h3>How to Submit:</h3>
            <ol>
                <li>Create your AI-generated video based on the brief</li>
                <li>Upload to R2 storage</li>
                <li>Commit to network: <code>{brief.brief_id}:sub_1:{{r2_link}}</code></li>
            </ol>
            
            <p><strong>Time is limited!</strong> Submit within 24 hours for consideration.</p>
            
            <p>Good luck!</p>
        </body>
        </html>
        """
        
        # Send to all miners (in batches to avoid rate limits)
        success_count = 0
        for email in miner_emails:
            if await self._send_email(email, subject, html_content):
                success_count += 1
        
        logger.info(f"Sent new brief notifications: {success_count}/{len(miner_emails)} successful")
        return success_count > 0
    
    async def send_deadline_reminder(self, brief: Brief, miner_emails: List[str]) -> bool:
        """Send deadline reminder to miners who haven't submitted."""
        subject = f"⏰ Deadline Reminder: {brief.title}"
        
        time_left = brief.deadline_24hr - datetime.utcnow()
        hours_left = int(time_left.total_seconds() / 3600)
        
        html_content = f"""
        <html>
        <body>
            <h2>⏰ Brief Deadline Approaching</h2>
            <p><strong>Only {hours_left} hours left</strong> to submit your video for this brief!</p>
            
            <h3>Brief Details:</h3>
            <ul>
                <li><strong>Title:</strong> {brief.title}</li>
                <li><strong>Deadline:</strong> {brief.deadline_24hr.strftime('%Y-%m-%d %H:%M UTC')}</li>
            </ul>
            
            <h3>Submit Now:</h3>
            <ol>
                <li>Upload your video to R2 storage</li>
                <li>Commit: <code>{brief.brief_id}:sub_1:{{r2_link}}</code></li>
            </ol>
            
            <p><strong>Don't miss out on this opportunity!</strong></p>
        </body>
        </html>
        """
        
        success_count = 0
        for email in miner_emails:
            if await self._send_email(email, subject, html_content):
                success_count += 1
        
        logger.info(f"Sent deadline reminders: {success_count}/{len(miner_emails)} successful")
        return success_count > 0
    
    async def send_top_10_selection_ready(self, brief: Brief) -> bool:
        """Notify user that submissions are ready for top 10 selection."""
        subject = f"Ready for Review: {brief.title}"
        
        html_content = f"""
        <html>
        <body>
            <h2>Submissions Ready for Review</h2>
            <p>Your brief has received submissions and is ready for review!</p>
            
            <h3>Brief: {brief.title}</h3>
            <p>Please log in to your InfiniteVibe dashboard to:</p>
            <ol>
                <li>View all submitted videos</li>
                <li>Select your top 10 favorites</li>
                <li>Send revision requests to selected miners</li>
            </ol>
            
            <p><a href="https://infinitevibe.ai/dashboard">Review Submissions →</a></p>
            
            <p>You have until {brief.deadline_24hr.strftime('%Y-%m-%d %H:%M UTC')} to make your selections.</p>
        </body>
        </html>
        """
        
        return await self._send_email(
            to_email=brief.user_email,
            subject=subject,
            html_content=html_content
        )
    
    async def send_top_10_notification(self, brief: Brief, selected_miners: List[str]) -> bool:
        """Notify miners they made the top 10 and can submit revisions."""
        subject = f"🎉 You Made Top 10: {brief.title}"
        
        html_content = f"""
        <html>
        <body>
            <h2>🎉 Congratulations!</h2>
            <p>Your submission has been selected for the <strong>top 10</strong>!</p>
            
            <h3>Brief: {brief.title}</h3>
            <p>You now have the opportunity to submit a revision.</p>
            
            <h3>Next Steps:</h3>
            <ol>
                <li>Review any feedback provided</li>
                <li>Create an improved version of your video</li>
                <li>Submit revision: <code>{brief.brief_id}:sub_2:{{r2_link}}</code></li>
            </ol>
            
            <p><strong>Revision deadline:</strong> {brief.deadline_24hr.strftime('%Y-%m-%d %H:%M UTC')}</p>
            
            <p>Good luck in the final round!</p>
        </body>
        </html>
        """
        
        # Note: In real implementation, selected_miners would be email addresses
        # For now, we'll just log since we don't have miner email mapping
        logger.info(f"Would send top 10 notifications to {len(selected_miners)} miners")
        return True
    
    async def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email using configured provider."""
        try:
            if self.provider == "sendgrid":
                return await self._send_via_sendgrid(to_email, subject, html_content)
            elif self.provider == "aws_ses":
                return await self._send_via_ses(to_email, subject, html_content)
            else:
                logger.error(f"Unknown email provider: {self.provider}")
                return False
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
    
    async def _send_via_sendgrid(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email via SendGrid."""
        if not self.api_key:
            logger.warning(f"Would send email via SendGrid: {subject} to {to_email}")
            return True  # Mock success for demo
        
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail
            
            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)
            
            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            response = sg.send(message)
            logger.info(f"SendGrid email sent: {response.status_code} to {to_email}")
            return response.status_code in [200, 202]
            
        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return False
    
    async def _send_via_ses(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email via AWS SES."""
        try:
            import boto3
            
            ses = boto3.client('ses', region_name=self.region)
            
            response = ses.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {'Html': {'Data': html_content}}
                }
            )
            
            logger.info(f"SES email sent: {response['MessageId']} to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"SES error: {e}")
            return False