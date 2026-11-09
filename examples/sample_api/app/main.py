from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field


class ItemInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=200)


class Item(ItemInput):
    id: int


def create_app() -> FastAPI:
    app = FastAPI(title="API de ejemplo - Gestión de elementos", version="1.0.0")
    items: dict[int, Item] = {}
    next_id = 1

    @app.post(
        "/items",
        response_model=Item,
        status_code=status.HTTP_201_CREATED,
        operation_id="create_item",
    )
    def create_item(item_input: ItemInput) -> Item:
        nonlocal next_id
        item = Item(id=next_id, **item_input.model_dump())
        items[item.id] = item
        next_id += 1
        return item

    @app.get("/items", response_model=list[Item], operation_id="list_items")
    def list_items() -> list[Item]:
        return list(items.values())

    @app.get("/items/{item_id}", response_model=Item, operation_id="get_item")
    def get_item(item_id: int) -> Item:
        item = items.get(item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento no encontrado")
        return item

    @app.put("/items/{item_id}", response_model=Item, operation_id="update_item")
    def update_item(item_id: int, item_input: ItemInput) -> Item:
        if item_id not in items:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento no encontrado")
        item = Item(id=item_id, **item_input.model_dump())
        items[item_id] = item
        return item

    @app.delete(
        "/items/{item_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_item",
    )
    def delete_item(item_id: int) -> Response:
        if item_id not in items:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento no encontrado")
        del items[item_id]
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


app = create_app()
