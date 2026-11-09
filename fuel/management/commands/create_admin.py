from secrets import token_urlsafe

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from fuel.models import Admin


class Command(BaseCommand):
    help = "Create an administrator and display the API key once."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        username = options["username"].strip()
        if not username or len(username) > 150:
            raise CommandError("Username must contain 1 to 150 characters.")

        key = token_urlsafe(32)
        try:
            Admin.objects.create(username=username, api_key_hash=make_password(key))
        except IntegrityError as error:
            raise CommandError("An administrator with this username already exists.") from error

        self.stdout.write(key)
