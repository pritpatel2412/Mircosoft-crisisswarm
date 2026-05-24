"""Configuration loader for CrisisSwarm.

This file defines the settings used across the project and reads
secrets from environment variables or a `.env` file. DO NOT commit
real credentials to git — this file is added to `.gitignore`.

Every value is read from the environment so deployment services
like Azure App Service can provide credentials via secure settings.
"""
from dataclasses import dataclass
import os
from typing import Optional

try:
	# optional convenience for local development
	from dotenv import load_dotenv
	load_dotenv()
except Exception:
	pass


@dataclass
class Settings:
	"""Application settings read from environment variables.

	All credentials must be supplied by the environment in production.
	"""
	AZURE_OPENAI_ENDPOINT: Optional[str] = None
	AZURE_OPENAI_KEY: Optional[str] = None
	AZURE_MAPS_KEY: Optional[str] = None
	AZURE_CLIENT_ID: Optional[str] = None
	AZURE_CLIENT_SECRET: Optional[str] = None
	AZURE_TENANT_ID: Optional[str] = None
	AZURE_OPENAI_DEPLOYMENT: Optional[str] = "gpt-4o"
	STREAMLIT_PORT: Optional[int] = 8501
	SERVICE_NAME: Optional[str] = "CrisisSwarm"


def load_settings() -> Settings:
	"""Load settings from environment variables.

	Returns:
		Settings: populated settings dataclass
	"""
	def getenv(name: str, default=None):
		val = os.environ.get(name, default)
		if val == "" or val == "<placeholder>":
			return default
		return val

	s = Settings(
		AZURE_OPENAI_ENDPOINT=getenv("AZURE_OPENAI_ENDPOINT"),
		AZURE_OPENAI_KEY=getenv("AZURE_OPENAI_KEY"),
		AZURE_MAPS_KEY=getenv("AZURE_MAPS_KEY"),
		AZURE_CLIENT_ID=getenv("AZURE_CLIENT_ID"),
		AZURE_CLIENT_SECRET=getenv("AZURE_CLIENT_SECRET"),
		AZURE_TENANT_ID=getenv("AZURE_TENANT_ID"),
		AZURE_OPENAI_DEPLOYMENT=getenv("AZURE_OPENAI_DEPLOYMENT") or "gpt-4o",
		STREAMLIT_PORT=int(getenv("STREAMLIT_PORT", 8501)),
		SERVICE_NAME=getenv("SERVICE_NAME", "CrisisSwarm"),
	)

	# Basic sanity warning (does not reveal secrets)
	if not s.AZURE_OPENAI_ENDPOINT or not s.AZURE_OPENAI_KEY:
		print("WARNING: Azure OpenAI endpoint/key not set. Set via environment variables or .env file.")

	return s


# module-level settings object for easy import
settings = load_settings()


def require_env_or_raise(name: str) -> str:
	"""Return an environment variable or raise an informative error.

	This helper is useful in places where the app cannot proceed without
	a particular credential.
	"""
	val = os.environ.get(name)
	if not val:
		raise EnvironmentError(f"Required environment variable '{name}' is not set.")
	return val


if __name__ == "__main__":
	# quick local check
	print("Loaded settings (redacted):")
	print("AZURE_OPENAI_ENDPOINT:", "set" if settings.AZURE_OPENAI_ENDPOINT else "NOT SET")
	print("AZURE_MAPS_KEY:", "set" if settings.AZURE_MAPS_KEY else "NOT SET")
