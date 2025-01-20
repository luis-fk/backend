from rest_framework.views import APIView
from rest_framework.response import Response
from . import serializers

class HelloWorldView(APIView):
    def get(self, request, *args, **kwargs):
        serializer = serializers.HelloWorldSerializer({'message': 'Hello, World!'})
        return Response(serializer.data)
