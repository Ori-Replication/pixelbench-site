distant = new_canvas(128, 128, name='sailboat_and_gulls')
distant.line(96, 39, 96, 56, '#f4fbff')
distant.poly([(94,41),(94,52),(85,52)], '#ffffff')
distant.line(92, 45, 88, 51, '#d2edf8')
distant.poly([(98,44),(104,52),(98,52)], '#fff5d9')
distant.poly([(85,54),(105,54),(102,57),(89,57)], '#e5f5ee')
distant.line(88,57,102,57,'#165c9c')
distant.line(91,59,101,59,'#58b9db')
distant.line(95,61,100,61,'#53ced7')
for x, y, s in [(57,15,1),(77,23,0)]:
    distant.line(x-5,y-2,x-3,y-2,'#ffffff')
    distant.line(x-3,y-2,x,y+1,'#ffffff')
    distant.line(x,y+1,x+3,y-2,'#ffffff')
    distant.line(x+3,y-2,x+5,y-2,'#ffffff')
    distant.set(x,y+2,'#368fbc')

props = new_canvas(128, 128, name='beach_objects')
props.ellipse(43,106,25,7,'#d5ac68')
props.ellipse(41,104,20,5,'#c49c64')
props.line(36,73,39,103,'#99694f')
props.line(35,73,38,102,'#fff0b5')
props.set(38,104,'#99694f')

# Perspective towel, with woven stripes and short fringe.
props.poly([(78,94),(99,99),(89,123),(65,116)], '#d5ac68')
corners = [(77,91),(99,96),(89,121),(65,114)]
props.poly(corners, '#fff9dd')
for t0, t1 in [(0.08,0.2),(0.34,0.46),(0.6,0.72),(0.86,0.96)]:
    def towel_point(t, right):
        a,b = ((99,96),(89,121)) if right else ((77,91),(65,114))
        return (round(a[0]+(b[0]-a[0])*t), round(a[1]+(b[1]-a[1])*t))
    props.poly([towel_point(t0,False),towel_point(t0,True),towel_point(t1,True),towel_point(t1,False)], '#278eae')
props.line(77,91,99,96,'#ffffff')
props.line(65,114,89,121,'#e9eee0')
for x,y in [(66,115),(70,116),(74,117),(78,118),(82,120),(86,121)]:
    props.line(x,y,x-1,y+2,'#fff9dd')

# Two individually shaded sandals and contrasting Y straps.
for x,y in [(105,106),(116,102)]:
    props.ellipse(x+1,y+2,3,6,'#d5ac68')
    props.ellipse(x,y,3,6,'#174f6a')
    props.ellipse(x,y-1,2,5,'#37afbc')
    props.line(x-2,y-2,x,y+1,'#ffecb5')
    props.line(x,y+1,x+2,y-3,'#ffecb5')
    props.set(x,y+2,'#fff9dd')

# The canopy silhouette and alternating curved radial fabric panels.
props.poly([(9,80),(13,73),(19,66),(27,62),(35,60),(44,63),(53,69),(61,79),(62,82),(53,85),(44,83),(35,86),(25,83),(17,85)], '#b74150')
props.poly([(10,79),(15,71),(25,64),(35,61),(24,70),(18,80)], '#fff9dd')
props.poly([(18,80),(24,70),(35,61),(31,70),(28,81)], '#ef5860')
props.poly([(28,81),(31,70),(35,61),(39,70),(43,81)], '#ffffff')
props.poly([(43,81),(39,70),(35,61),(47,68),(53,81)], '#ef5860')
props.poly([(53,81),(47,68),(35,61),(44,64),(53,70),(61,80)], '#fff9dd')
props.poly([(10,79),(18,80),(17,83),(13,82)], '#d2dedb')
props.poly([(18,80),(28,81),(25,84),(21,83)], '#d94355')
props.poly([(28,81),(43,81),(39,84),(35,85),(30,83)], '#d2dedb')
props.poly([(43,81),(53,81),(51,84),(46,83)], '#d94355')
props.poly([(53,81),(61,80),(59,83),(55,84)], '#d2dedb')
props.line(20,69,29,64,'#ffffff')
props.line(31,67,34,63,'#ff8580')
props.line(40,65,49,70,'#ff8580')
props.rect(34,58,3,3,'#fff0b5')
props.set(35,58,'#ffffff')

# Small sunlit shells in the open sand.
for x,y in [(14,117),(57,113),(108,89)]:
    props.line(x-2,y,x+2,y,'#e9bd72')
    props.line(x-1,y-1,x+1,y-1,'#fff9dd')
    props.set(x,y-2,'#ffffff')
    props.set(x+1,y,'#f2a58b')
scene = flatten([sky, clouds, water, sand, distant, props], name='summer_seaside')
print(save('summer_seaside', canvas=scene))
print(scene.stats_text())
