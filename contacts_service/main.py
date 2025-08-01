from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List
import uvicorn
import time
import os
import pika
import json
import uuid
import asyncio

# Database configuration - usando as credenciais do docker-compose.yml
def get_database_url():
    # Credenciais conforme definido no docker-compose.yml
    user = "postgres"
    password = "postgres"
    host = "postgres"  # nome do container
    port = "5432"
    database = "contacts_db"
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"

DATABASE_URL = get_database_url()

# Função para criar engine com retry (aguardar o postgres estar pronto)
def create_db_engine():
    max_retries = 30
    retry_interval = 2
    
    print(f"🔄 Tentando conectar ao PostgreSQL: {DATABASE_URL}")
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(DATABASE_URL, echo=False)
            # Testa a conexão - usando text() para SQLAlchemy 2.x
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Conexão com PostgreSQL estabelecida com sucesso!")
            return engine
        except Exception as e:
            print(f"⏳ Tentativa {attempt + 1}/{max_retries} falhou: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                print("❌ Falha ao conectar ao PostgreSQL após todas as tentativas")
                raise e

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database model
class ContactDB(Base):
    __tablename__ = "contacts"
    
    name = Column(String, nullable=False)
    phone = Column(String, primary_key=True, index=True)
    address = Column(String, nullable=False)
    region = Column(String, nullable=False)
    is_favorite = Column(Boolean, default=False)

# Pydantic models
class ContactBase(BaseModel):
    name: str
    phone: str
    address: str

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    name: str = None
    phone: str = None
    address: str = None

class Contact(ContactBase):
    region: str
    is_favorite: bool
    
    class Config:
        from_attributes = True

# Create tables
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tabelas criadas/verificadas com sucesso!")
except Exception as e:
    print(f"❌ Erro ao criar tabelas: {e}")
    raise e

app = FastAPI(title="Contacts Service API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# RabbitMQ configuration
def get_rabbitmq_connection():
    rabbitmq_host = "rabbitmq" if os.getenv("DOCKER_ENV") else "localhost"
    max_retries = 30
    retry_interval = 2
    
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=rabbitmq_host)
            )
            print("✅ Conexão com RabbitMQ estabelecida com sucesso!")
            return connection
        except Exception as e:
            print(f"⏳ Tentativa {attempt + 1}/{max_retries} para conectar ao RabbitMQ falhou: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                print("❌ Falha ao conectar ao RabbitMQ após todas as tentativas")
                raise e

# Helper function to get region from DDD API via RabbitMQ
async def get_region_from_ddd(phone: str) -> str:
    def rpc_call():
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        
        # Declare queues
        channel.queue_declare(queue='ddd_request')
        
        # Create callback queue for response
        result = channel.queue_declare(queue='', exclusive=True)
        callback_queue = result.method.queue
        
        response = {}
        
        def on_response(ch, method, props, body):
            if props.correlation_id == correlation_id:
                response['result'] = json.loads(body)
        
        channel.basic_consume(
            queue=callback_queue,
            on_message_callback=on_response,
            auto_ack=True
        )
        
        # Send request
        correlation_id = str(uuid.uuid4())
        channel.basic_publish(
            exchange='',
            routing_key='ddd_request',
            properties=pika.BasicProperties(
                reply_to=callback_queue,
                correlation_id=correlation_id,
            ),
            body=json.dumps({"phone": phone})
        )
        
        # Wait for response
        start_time = time.time()
        timeout = 10  # 10 seconds timeout
        
        while not response and (time.time() - start_time) < timeout:
            connection.process_data_events(time_limit=1)
        
        connection.close()
        
        if response:
            return response['result'].get('region', 'Região não encontrada')
        else:
            return 'Região não encontrada'
    
    # Run the blocking RabbitMQ call in a thread pool
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, rpc_call)

# CRUD Endpoints
@app.post("/contacts/", response_model=Contact)
async def create_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    # Check if phone already exists
    existing_contact = db.query(ContactDB).filter(ContactDB.phone == contact.phone).first()
    if existing_contact:
        raise HTTPException(status_code=400, detail="Telefone já cadastrado")
    
    # Get region from DDD API
    region = await get_region_from_ddd(contact.phone)
    if region == "Região não encontrada":
        raise HTTPException(status_code=400, detail="DDD não encontrado. Verifique o número digitado.")
    
    # Create new contact
    db_contact = ContactDB(
        name=contact.name,
        phone=contact.phone,
        address=contact.address,
        region=region,
        is_favorite=False
    )
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@app.get("/contacts/", response_model=List[Contact])
def get_contacts(db: Session = Depends(get_db)):
    contacts = db.query(ContactDB).all()
    return contacts

@app.get("/contacts/{phone}", response_model=Contact)
def get_contact(phone: str, db: Session = Depends(get_db)):
    contact = db.query(ContactDB).filter(ContactDB.phone == phone).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    return contact

@app.put("/contacts/{phone}", response_model=Contact)
async def update_contact(phone: str, contact_update: ContactUpdate, db: Session = Depends(get_db)):
    contact = db.query(ContactDB).filter(ContactDB.phone == phone).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    
    # Update fields if provided
    if contact_update.name is not None:
        contact.name = contact_update.name
    if contact_update.address is not None:
        contact.address = contact_update.address
    if contact_update.phone is not None:
        # Check if new phone already exists
        existing_contact = db.query(ContactDB).filter(
            ContactDB.phone == contact_update.phone
        ).first()
        if existing_contact and existing_contact.phone != phone:
            raise HTTPException(status_code=400, detail="Telefone já cadastrado")
        
        # Update region if phone changed
        region = await get_region_from_ddd(contact_update.phone)
        if region == "Região não encontrada":
            raise HTTPException(status_code=400, detail="DDD não encontrado. Verifique o número digitado.")
        
        # Delete old record and create new one (since phone is primary key)
        db.delete(contact)
        db.commit()
        
        new_contact = ContactDB(
            name=contact.name,
            phone=contact_update.phone,
            address=contact.address,
            region=region,
            is_favorite=contact.is_favorite
        )
        db.add(new_contact)
        db.commit()
        db.refresh(new_contact)
        return new_contact
    
    db.commit()
    db.refresh(contact)
    return contact

@app.delete("/contacts/{phone}")
def delete_contact(phone: str, db: Session = Depends(get_db)):
    contact = db.query(ContactDB).filter(ContactDB.phone == phone).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    
    db.delete(contact)
    db.commit()
    return {"message": "Contato deletado com sucesso"}

@app.patch("/contacts/{phone}/favorite")
def toggle_favorite(phone: str, db: Session = Depends(get_db)):
    contact = db.query(ContactDB).filter(ContactDB.phone == phone).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    
    contact.is_favorite = not contact.is_favorite
    db.commit()
    db.refresh(contact)
    return contact

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3004)
