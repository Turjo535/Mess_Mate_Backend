from django.db import models
from django.utils import timezone
# from User_Authentication.models import Member
from Mess_Management.models import Mess, Mess_Members
# Create your models here.


class MemberDeposit(models.Model):
    member = models.ForeignKey(Mess_Members, on_delete=models.CASCADE)
    add_by= models.ForeignKey(Mess_Members, on_delete=models.CASCADE, related_name='added_by')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    section = models.CharField(choices=[('Bazar', 'Bazar'), ('Utilities', 'Utilities')], max_length=20, default='Bazar')
    deposit_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Member ID: {self.member.id}, Amount: {self.amount}, Date: {self.deposit_date}"

class MessBazar(models.Model):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE)
    member = models.ForeignKey(Mess_Members, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=100)
    product_quantity = models.CharField(max_length=50)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_image = models.ImageField(upload_to='bazar_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Member ID: {self.member.id}, Product: {self.product_name}, Price: {self.product_price}"


class MessUtilities(models.Model):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE)
    utility_name = models.CharField(max_length=100)
    description = models.TextField(default="No description provided.")
    utility_cost = models.DecimalField(max_digits=10, decimal_places=2)
    utility_date = models.DateTimeField(auto_now_add=True)
    

    def __str__(self):
        return f"Mess ID: {self.mess.id}, Utility: {self.utility_name}, Cost: {self.utility_cost}"

class MessCycle(models.Model):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, default="Default Cycle Name")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    @property
    def is_active(self):
        """Returns True if current time is within cycle (start_date <= now <= end_date), False if past or future."""
        now = timezone.now()
        return self.start_date <= now <= self.end_date

    @property
    def is_over(self):
        """Returns True if current time has passed end_date."""
        now = timezone.now()
        return now > self.end_date

    def __str__(self):
        return f"Mess ID: {self.mess.id}, Start: {self.start_date}, End: {self.end_date}"