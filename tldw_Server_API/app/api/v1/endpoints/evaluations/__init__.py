"""Evaluations endpoint package exports and modular router attachment."""

from __future__ import annotations

from . import evaluations_unified as evaluations_unified_module
from .evaluations_recipes import recipes_router

router = evaluations_unified_module.router

if not getattr(router, "_recipe_routes_registered", False):
    router.include_router(recipes_router)
    recipe_routes = [
        route
        for route in router.routes
        if route.path.startswith("/evaluations/recipes")
        or route.path.startswith("/evaluations/recipe-runs")
    ]
    other_routes = [route for route in router.routes if route not in recipe_routes]
    router.routes[:] = recipe_routes + other_routes
    router._recipe_routes_registered = True

__all__ = ("router", "recipes_router")
