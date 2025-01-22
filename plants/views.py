from django.http import HttpRequest
from rest_framework.response import Response
from rest_framework.views import APIView
from views import serializers


class HelloWorldView(APIView):
    def get(self, request: HttpRequest, *args: list, **kwargs: dict) -> Response:
        serializer = serializers.HelloWorldSerializer({"message": "Hello, World!"})
        return Response(serializer.data)
