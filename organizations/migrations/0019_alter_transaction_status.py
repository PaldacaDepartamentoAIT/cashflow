from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0018_projectsharelink'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='status',
            field=models.CharField(choices=[('completado', 'Completado'), ('pendiente', 'Pendiente'), ('parcial', 'Parcial')], default='completado', max_length=20, verbose_name='Estado'),
        ),
    ]
