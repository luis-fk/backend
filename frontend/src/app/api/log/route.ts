import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { level, message, optionalParams = [], timestamp, url } = body;

    const logMessage = `[CLIENT-LOG] | ${timestamp} | ${level.toUpperCase()} | URL: ${url} | Message: ${message}`;

    switch (level) {
      case "error":
        console.error(logMessage, ...optionalParams);
        break;
      default:
        console.log(logMessage, ...optionalParams);
    }

    return new NextResponse(null, { status: 202 }); 
  } catch (error) {
    console.error("Error in /api/log:", error);
    return new NextResponse("Error processing log", { status: 500 });
  }
}
