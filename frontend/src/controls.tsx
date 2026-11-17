import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { Input } from '@/components/ui/input'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'

export function Pane({title,description,children,footer,className}:{title:string;description?:string;children:ReactNode;footer?:ReactNode;className?:string}){return <Card className={className}><CardHeader><CardTitle><h2>{title}</h2></CardTitle>{description&&<CardDescription>{description}</CardDescription>}</CardHeader><CardContent>{children}</CardContent>{footer&&<CardFooter>{footer}</CardFooter>}</Card>}
export function TextField({label,id,value,onChange,type='text',description,min,step,required=false}:{label:string;id:string;value:string|number;onChange:(v:string)=>void;type?:string;description?:string;min?:number;step?:number;required?:boolean}){return <Field><FieldLabel htmlFor={id}>{label}</FieldLabel><Input id={id} name={id} value={value} onChange={e=>onChange(e.target.value)} type={type} min={min} step={step} required={required} autoComplete={type==='password'?'current-password':'off'} spellCheck={false}/>{description&&<FieldDescription>{description}</FieldDescription>}</Field>}
export function Choice({label,id,value,onChange,options}:{label:string;id:string;value:string;onChange:(v:string)=>void;options:{value:string;label:string}[]}){return <Field><FieldLabel htmlFor={id}>{label}</FieldLabel><Select value={value} onValueChange={onChange}><SelectTrigger id={id}><SelectValue/></SelectTrigger><SelectContent><SelectGroup>{options.map(o=><SelectItem value={o.value} key={o.value}>{o.label}</SelectItem>)}</SelectGroup></SelectContent></Select></Field>}
export function ToggleSetting({label,id,value,onChange,description}:{label:string;id:string;value:boolean;onChange:(v:boolean)=>void;description?:string}){return <Field orientation="horizontal"><div className="flex min-w-0 flex-1 flex-col gap-1"><FieldLabel htmlFor={id}>{label}</FieldLabel>{description&&<FieldDescription>{description}</FieldDescription>}</div><Switch id={id} name={id} checked={value} onCheckedChange={onChange}/></Field>}
export function SaveButton({busy=false,busyLabel='Wird gespeichert …',children='Änderungen speichern',onClick}:{busy?:boolean;busyLabel?:string;children?:ReactNode;onClick?:()=>void}){return <Button type={onClick?'button':'submit'} size="lg" onClick={onClick} disabled={busy}>{busy&&<Spinner data-icon="inline-start"/>}{busy?busyLabel:children}</Button>}
export type Confirm = (title:string,description:string,run:()=>Promise<void>)=>void
