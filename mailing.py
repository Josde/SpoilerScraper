import boto3
from botocore.exceptions import ClientError
from app import db
# Replace sender@example.com with your "From" address.
# This address must be verified with Amazon SES.
SENDER = "Spoiler Notifications <spoilers@josde.me>"
def sendChapterMail(recipients, chapterNumber, chapterLink):
    SUBJECT = "{0} is out!".format(chapterNumber)
    BODY_TEXT = ("{0} is out! The link is here: {1}\r\n"
     "You can unsubscribe at any moment by entering your mail in: spoilers.josde.me/mail".format(chapterNumber, chapterLink)
     )
    BODY_CONTENT = """<html>
    <head></head>
    <body>
      <h1>{0} is out!</h1>
      <p>The link is here:
        <a href='{1}'>TCBScans</a>
      </p>
      <p>You can unsubscribe at any moment by entering your mail again in:
        <a href='https://spoilers.josde.me/mail'>spoilers.josde.me/mail</a>
      </p>
    </body>
    </html>
                """.format(chapterNumber, chapterLink)
    print("[Mail] Sending chapter mail to {0} ({1} recipients)".format(recipients, len(recipients)))
    while len(recipients) != 0:
        currentList = []
        for n in range(0, 50):
            if (len(recipients)) == 0:
                break
            currentList.append(recipients.pop(0))
        print("[Mail] Sending chapter mail to {0} recipients, {1} left.".format(len(currentList), len(recipients)))
        print('Current list is: {0}'.format(currentList))
        sendMail(SUBJECT, currentList, BODY_TEXT, BODY_CONTENT, bcc=True)
        #TODO: Rate limiting

def sendMail(subject, recipients, content, htmlContent, bcc=True):
    # Replace recipient@example.com with a "To" address. If your account
    # is still in the sandbox, this address must be verified.
    if len(recipients) == 0:
        print("Tried to send an email with no recipient, returning.")
        return

    if bcc:
        destination = {
            'BccAddresses': recipients,
        }
    else:
        destination = {
            'ToAddresses': recipients,
        }
    # Specify a configuration set. If you do not want to use a configuration
    # set, comment the following variable, and the
    # ConfigurationSetName=CONFIGURATION_SET argument below.
    CONFIGURATION_SET = "ConfigSet"

    # If necessary, replace us-west-2 with the AWS Region you're using for Amazon SES.
    AWS_REGION = "us-east-2"

    # The subject line for the email.
    SUBJECT = subject

    # The email body for recipients with non-HTML email clients.
    BODY_TEXT = content

    # The HTML body of the email.
    BODY_HTML = htmlContent

    # The character encoding for the email.
    CHARSET = "UTF-8"

    # Create a new SES resource and specify a region.
    client = boto3.client('ses', region_name=AWS_REGION)

    # Try to send the email.
    try:
        # Provide the contents of the email.
        response = client.send_email(
            Destination=destination,
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
            # If you are not using a configuration set, comment or delete the
            # following line
            # ConfigurationSetName=CONFIGURATION_SET,
        )
    # Display an error if something goes wrong.
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])

def sendVerificationMail(recipients, uuid, deactivation):
    if not deactivation:
        SUBJECT = "Mailing list verification"
        BODY_TEXT = ("This email address has been signed up for the spoilers.josde.me mailing list.\r\n"
         "To verify and complete the sign-up, go to the following address: https://spoilers.josde.me/validate?uuid={0}&email={1}".format(uuid, recipients)
         )
        BODY_CONTENT = """<html>
        <head></head>
        <body>
          <p>This email address has been signed up for the spoilers.josde.me mailing list.
          </p>
          <p>To verify and complete the sign-up, go to the following address: 
            <a href='https://spoilers.josde.me/validate?uuid={0}&email={1}'>https://spoilers.josde.me/validate?uuid={0}&email={1}</a>
          </p>
        </body>
        </html>
                    """.format(uuid, recipients)
    else:
        SUBJECT = "Mailing list deactivation"
        BODY_TEXT = ("You have requested deactivation for the spoilers.josde.me mailing list.\r\n"
                     "To verify and complete the deactivation, go to the following address: https://spoilers.josde.me/deactivate?uuid={0}&email={1}".format(
            uuid, recipients)
                     )
        BODY_CONTENT = """<html>
                <head></head>
                <body>
                  <p>You have requested deactivation for the spoilers.josde.me mailing list.
                  </p>
                  <p>To verify and complete the deactivation, go to the following address: 
                    <a href='https://spoilers.josde.me/deactivate?uuid={0}&email'>https://spoilers.josde.me/deactivate?uuid={0}&email={1}</a>
                  </p>
                </body>
                </html>
                            """.format(uuid, recipients)
    sendMail(SUBJECT, [recipients], BODY_TEXT, BODY_CONTENT, bcc=False)
