from django.apps import AppConfig
import threading
class MealPlannerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'meal_planner'


    # def ready(self):
    #     from django.conf import settings
    #     from meal_planner.views import AddThreadToProcessingOrWaiting
    #     import redis
    #     import time
    #     r = redis.StrictRedis(host="127.0.0.1", port = 6379, db = 0, decode_responses = True)

    #     if getattr(settings, 'START_MEAL_THREAD', True):
    #         thread = threading.Thread(
    #             target=AddThreadToProcessingOrWaiting,
    #             args=(None,),  # request not needed
    #             daemon=True
    #         )
    #         thread.start()
