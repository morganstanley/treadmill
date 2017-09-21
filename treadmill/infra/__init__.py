import pkg_resources
from treadmill.infra import connection


SCRIPT_DIR = pkg_resources.resource_filename(__name__, 'setup/scripts/')


def create_iam_role(name, description=''):
    iam_conn = connection.Connection('iam')
    assume_role_policy_document = '''{ \
            "Version": "2012-10-17", \
            "Statement": { \
                "Effect": "Allow", \
                "Principal": {"Service": "ec2.amazonaws.com"}, \
                "Action": "sts:AssumeRole" \
            } \
        } \
    '''
    role = iam_conn.create_role(
        RoleName=name,
        AssumeRolePolicyDocument=assume_role_policy_document,
        Description=description
    )
    iam_conn.attach_role_policy(
        RoleName=name,
        PolicyArn='arn:aws:iam::aws:policy/AmazonEC2FullAccess'
    )
    iam_conn.create_instance_profile(
        InstanceProfileName=name
    )
    iam_conn.add_role_to_instance_profile(
        RoleName=name,
        InstanceProfileName=name
    )
    return role


def get_iam_role(name, create=False):
    iam_conn = connection.Connection('iam')
    try:
        return iam_conn.get_role(RoleName=name)
    except iam_conn.exceptions.NoSuchEntityException:
        if create:
            return create_iam_role(name)
